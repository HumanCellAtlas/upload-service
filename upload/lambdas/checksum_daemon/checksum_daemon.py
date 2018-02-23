import json
import os
import re

import boto3
from six.moves import urllib

from ..common.event_notifier import EventNotifier
from ...common.upload_area import UploadArea
from ...common.ingest_notifier import IngestNotifier
from ...common.checksum import UploadedFileChecksummer
from ...common.logging import get_logger
from ...common.batch import JobDefinition

logger = get_logger(__name__)

KB = 1024
MB = KB * KB
GB = MB * KB

batch = boto3.client('batch')


class ChecksumDaemon:

    RECOGNIZED_S3_EVENTS = ('ObjectCreated:Put', 'ObjectCreated:CompleteMultipartUpload')

    def __init__(self, context):
        logger.debug("Ahm ahliiivvve!")
        self._read_environment()
        self.upload_area = None
        self.uploaded_file = None

    def _read_environment(self):
        self.use_batch_if_larger_than = int(os.environ['CSUM_USE_BATCH_FILE_SIZE_THRESHOLD_GB']) * GB
        self.deployment_stage = os.environ['DEPLOYMENT_STAGE']
        self.bucket_name = os.environ['BUCKET_NAME']
        self.job_q_arn = os.environ['CSUM_JOB_Q_ARN']
        self.job_role_arn = os.environ['CSUM_JOB_ROLE_ARN']
        self.docker_image = os.environ['CSUM_DOCKER_IMAGE']
        self.ingest_amqp_server = os.environ['INGEST_AMQP_SERVER']

    def consume_event(self, event):
        for record in event['Records']:
            if record['eventName'] not in self.RECOGNIZED_S3_EVENTS:
                logger.warning(f"Unexpected event: {record['eventName']}")
                continue
            file_key = record['s3']['object']['key']
            self._find_file(file_key)
            self._checksum_file()

    def _find_file(self, file_key):
        logger.debug(f"File: {file_key}")
        area_uuid = file_key.split('/')[0]
        filename = urllib.parse.unquote(file_key[len(area_uuid) + 1:])
        self.upload_area = UploadArea(area_uuid)
        self.uploaded_file = self.upload_area.uploaded_file(filename)

    def _checksum_file(self):
        if self.uploaded_file.size > self.use_batch_if_larger_than:
            logger.debug("Scheduling checksimming batch job")
            self.schedule_checksumming(self.uploaded_file)
        else:
            checksummer = UploadedFileChecksummer(self.uploaded_file)
            checksums = checksummer.checksum(report_progress=True)
            self.uploaded_file.checksums = checksums
            tags = self.uploaded_file.save_tags()
            logger.info(f"Checksummed and tagged with: {tags}")
            self._notify_ingest()
            EventNotifier.notify(f"{self.upload_area.uuid} checksummed {self.uploaded_file.name}")

    def _notify_ingest(self):
        payload = self.uploaded_file.info()
        status = IngestNotifier().file_was_uploaded(payload)
        logger.info(f"Notified Ingest: payload={payload}, status={status}")

    JOB_NAME_ALLOWABLE_CHARS = '[^\w-]'

    def schedule_checksumming(self, uploaded_file):
        command = ['python', '/checksummer.py', uploaded_file.s3url]
        environment = {
            'BUCKET_NAME': self.bucket_name,
            'DEPLOYMENT_STAGE': self.deployment_stage,
            'INGEST_AMQP_SERVER': self.ingest_amqp_server
        }
        job_name = "-".join(["csum", self.deployment_stage, uploaded_file.upload_area.uuid, uploaded_file.name])
        self._enqueue_batch_job(queue_arn=self.job_q_arn,
                                job_name=job_name,
                                job_defn=self._find_or_create_job_definition(),
                                command=command,
                                environment=environment)

    def _find_or_create_job_definition(self):
        job_defn = JobDefinition(docker_image=self.docker_image, deployment=self.deployment_stage)
        job_defn.find_or_create(self.job_role_arn)
        return job_defn

    def _enqueue_batch_job(self, queue_arn, job_name, job_defn, command, environment):
        job_name = re.sub(self.JOB_NAME_ALLOWABLE_CHARS, "", job_name)[0:128]
        job = batch.submit_job(
            jobName=job_name,
            jobQueue=queue_arn,
            jobDefinition=job_defn.arn,
            containerOverrides={
                'command': command,
                'environment': [dict(name=k, value=v) for k, v in environment.items()]
            }
        )
        print(f"Enqueued job {job_name} [{job['jobId']}] using job definition {job_defn.arn}:")
        print(json.dumps(job))
        return job['jobId']
