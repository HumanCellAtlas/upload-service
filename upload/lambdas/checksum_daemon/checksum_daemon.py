import json
import logging
import os
import re
import time
import uuid

import boto3
from six.moves import urllib

from ...common.batch import JobDefinition
from ...common.checksum_event import ChecksumEvent
from ...common.dss_checksums import DssChecksums
from ...common.ingest_notifier import IngestNotifier
from ...common.retry import retry_on_aws_too_many_requests
from ...common.upload_area import UploadArea
from ...common.upload_config import UploadConfig, UploadVersion

logger = logging.getLogger(__name__)

KB = 1024
MB = KB * KB
GB = MB * KB

batch = boto3.client('batch')


class ChecksumDaemon:
    RECOGNIZED_S3_EVENTS = (
        'ObjectCreated:Put',
        'ObjectCreated:CompleteMultipartUpload',
        'ObjectCreated:Copy'
    )
    USE_BATCH_IF_FILE_LARGER_THAN = 10 * GB

    def __init__(self, context):
        self.request_id = context.aws_request_id
        logger.debug(f"Ahm ahliiivvve! request_id={self.request_id}")
        self.config = UploadConfig()
        self.upload_service_version = UploadVersion().upload_service_version
        logger.debug("UPLOAD_SERVICE_VERSION: {}".format(self.upload_service_version))
        self._read_environment()
        self.upload_area = None
        self.uploaded_file = None

    def _read_environment(self):
        self.deployment_stage = os.environ['DEPLOYMENT_STAGE']
        self.docker_image = os.environ['CSUM_DOCKER_IMAGE']
        self.api_host = os.environ["API_HOST"]

    def consume_events(self, events):
        for event in events['Records']:
            if event['eventName'] in self.RECOGNIZED_S3_EVENTS:
                self._consume_event(event)
            else:
                logger.warning(f"Unexpected event: {event['eventName']}")

    def _consume_event(self, event):
        file_key = event['s3']['object']['key']
        self._get_file_record(file_key)

        if self.uploaded_file.checksums:
            checksums = DssChecksums(s3_object=self.uploaded_file.s3object, checksums=self.uploaded_file.checksums)
            checksums.save_as_tags_on_s3_object()
            self._notify_ingest()
        else:
            if self._file_is_small_enough_to_checksum_inline():
                checksums = self._compute_checksums()
                checksums.save_as_tags_on_s3_object()
                self.uploaded_file.checksums = dict(checksums)  # saves to DB
                self._notify_ingest()
            else:
                self._schedule_checksumming()

    def _get_file_record(self, file_key):
        logger.debug(f"file_key={file_key}")
        area_uuid = file_key.split('/')[0]
        filename = urllib.parse.unquote(file_key[len(area_uuid) + 1:])
        self.upload_area = UploadArea(area_uuid)
        logger.debug(self.upload_area)
        self.uploaded_file = self.upload_area.uploaded_file(filename)
        logger.debug(self.uploaded_file)
        logger.debug(f"UploadedFile checksums={self.uploaded_file.checksums}")

    def _file_is_small_enough_to_checksum_inline(self):
        return self.uploaded_file.size <= self.USE_BATCH_IF_FILE_LARGER_THAN

    def _notify_ingest(self):
        self._check_content_type()
        file_info = self.uploaded_file.info()
        notifier = IngestNotifier('file_uploaded', file_id=self.uploaded_file.db_id)
        status = notifier.format_and_send_notification(file_info)
        logger.info(f"Notified Ingest: file_info={file_info}, status={status}")

    CHECK_CONTENT_TYPE_INTERVAL = 6
    CHECK_CONTENT_TYPE_TIMES = 5

    """
    If the file's content_type doesn't have a 'dcp-type' suffix, refresh it a few times
    to see if it acquires one.  Due to AWSCLI/S3 failing to correctly apply content_type,
    we occasionally have to add it after the fact.  If it doesn't appear, proceed anyway.
    """

    def _check_content_type(self):
        naps_left = self.CHECK_CONTENT_TYPE_TIMES
        while naps_left > 0 and '; dcp-type=' not in self.uploaded_file.content_type:
            logger.debug(f"No dcp-type in content_type of file {self.uploaded_file.s3_key},"
                         f" checking {naps_left} more times")
            time.sleep(self.CHECK_CONTENT_TYPE_INTERVAL)
            naps_left -= 1
            self.uploaded_file.refresh()
        if '; dcp-type=' not in self.uploaded_file.content_type:
            logger.warning(f"Still no dcp-type in content_type of file {self.uploaded_file.s3_key} after 30s")

    def _compute_checksums(self):
        checksum_event = ChecksumEvent(checksum_id=str(uuid.uuid4()),
                                       file_id=self.uploaded_file.db_id,
                                       status="CHECKSUMMING")
        checksum_event.create_record()

        checksums = DssChecksums(s3_object=self.uploaded_file.s3object)
        checksums.compute(report_progress=True)

        checksum_event.status = "CHECKSUMMED"
        checksum_event.update_record()

        return checksums

    def _schedule_checksumming(self):
        logger.debug("Scheduling checksumming batch job")
        checksum_id = str(uuid.uuid4())
        command = ['python', '/checksummer.py', self.uploaded_file.s3url, self.uploaded_file.s3_etag]
        environment = {
            'API_HOST': self.api_host,
            'CHECKSUM_ID': checksum_id,
            'CONTAINER': 'DOCKER'
        }
        job_name = "-".join([
            "csum", self.deployment_stage, self.uploaded_file.upload_area.uuid, self.uploaded_file.name])
        job_id = self._enqueue_batch_job(queue_arn=self.config.csum_job_q_arn,
                                         job_name=job_name,
                                         command=command,
                                         environment=environment)

        checksum_event = ChecksumEvent(file_id=self.uploaded_file.db_id,
                                       checksum_id=checksum_id,
                                       job_id=job_id,
                                       status="SCHEDULED")
        checksum_event.create_record()

    def _find_or_create_job_definition(self):
        job_defn = JobDefinition(docker_image=self.docker_image, deployment=self.deployment_stage)
        job_defn.find_or_create(self.config.csum_job_role_arn)
        return job_defn

    JOB_NAME_ALLOWABLE_CHARS = '[^\w-]'

    @retry_on_aws_too_many_requests
    def _enqueue_batch_job(self, queue_arn, job_name, command, environment):
        job_name = re.sub(self.JOB_NAME_ALLOWABLE_CHARS, "", job_name)[0:128]
        job_defn = self._find_or_create_job_definition()
        job = batch.submit_job(
            jobName=job_name,
            jobQueue=queue_arn,
            jobDefinition=job_defn.arn,
            containerOverrides={
                'command': command,
                'environment': [dict(name=k, value=v) for k, v in environment.items()]
            }
        )
        logger.info(f"Enqueued job {job_name} [{job['jobId']}] using job definition {job_defn.arn}:")
        logger.info(json.dumps(job))
        return job['jobId']
