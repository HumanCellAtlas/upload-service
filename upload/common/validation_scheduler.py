import json
import os
import re
import urllib.parse
import uuid

import boto3
from tenacity import retry, wait_fixed, stop_after_attempt

from .uploaded_file import UploadedFile
from .batch import JobDefinition
from .retry import retry_on_aws_too_many_requests
from .validation_event import ValidationEvent
from .upload_config import UploadConfig
from .exceptions import UploadException
from .logging import get_logger

batch = boto3.client('batch')
sqs = boto3.resource('sqs')
# 1tb volume limit for staging files from s3 during validation process
KB = 1000
MB = KB * KB
GB = MB * KB
TB = GB * KB
MAX_FILE_SIZE_IN_BYTES = TB

logger = get_logger(__name__)


class ValidationScheduler:

    JOB_NAME_ALLOWABLE_CHARS = '[^\w-]'

    def __init__(self, upload_area_uuid: str, uploaded_files: list):
        self.upload_area_uuid = upload_area_uuid
        self.files = uploaded_files
        self.config = UploadConfig()

    @property
    def file_keys(self):
        return [f"{file.upload_area.uuid}/{urllib.parse.unquote(file.name)}" for file in self.files]

    @property
    def bucket(self):
        return self.file.upload_area.bucket_name

    @property
    def url_safe_file_keys(self):
        return [urllib.parse.quote(file_key) for file_key in self.file_keys]

    @property
    def file_s3_locations(self):
        return [f"s3://{self.bucket}/{file_key}" for file_key in self.url_safe_file_keys]

    @property
    def file_db_ids(self):
        return [file.db_id for file in self.files]

    def check_files_can_be_validated(self):
        files_size = 0
        for file in self.files:
            files_size += file.size
        return files_size < MAX_FILE_SIZE_IN_BYTES

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
    def add_to_validation_sqs(self, filenames: list, validator_image: str, env: dict, orig_val_id=None):
        validation_id = str(uuid.uuid4())
        payload = {
            'upload_area_uuid': self.upload_area_uuid,
            'filenames': filenames,
            'validation_id': validation_id,
            'validator_docker_image': validator_image,
            'environment': env,
            'orig_validation_id': orig_val_id
        }
        self._create_validation_event(validator_image, validation_id, orig_val_id)
        response = sqs.meta.client.send_message(QueueUrl=self.config.validation_q_url,
                                                MessageBody=json.dumps(payload))
        status = response['ResponseMetadata']['HTTPStatusCode']
        if status != 200:
            raise UploadException(status=500, title="Internal error",
                                  detail=f"Adding files {self.file_keys} was unsuccessful to \
                                          validation sqs {self.config.area_deletion_q_url} )")
        logger.info(f"added files {self.file_keys} to validation sqs")
        return validation_id

    def schedule_batch_validation(self, validation_id: str, docker_image: str, env: dict, orig_val_id=None) -> str:
        job_defn = self._find_or_create_job_definition_for_image(docker_image)
        env['DEPLOYMENT_STAGE'] = os.environ['DEPLOYMENT_STAGE']
        env['INGEST_API_KEY'] = os.environ['INGEST_API_KEY']
        env['API_HOST'] = os.environ['API_HOST']
        env['CONTAINER'] = 'DOCKER'
        if orig_val_id:
            # If there is an original validation id for a scheduled validation, we pass the original validation id
            # rather than the new validation db id into the env variables.
            # This allows ingest to correlate results for this file with the original validation id.
            env['VALIDATION_ID'] = orig_val_id
        else:
            env['VALIDATION_ID'] = validation_id
        command = ['/validator']
        for file_s3_loc in self.file_s3_locations:
            command.append(file_s3_loc)
        logger.info(f"scheduling batch job with {env}")
        self.batch_job_id = self._enqueue_batch_job(job_defn, command, env, validation_id)
        self._update_validation_event(docker_image, validation_id, orig_val_id)
        return validation_id

    def _create_validation_event(self, validator_docker_image, validation_id, orig_val_id, status="SCHEDULING_QUEUED"):
        validation_event = ValidationEvent(file_ids=self.file_db_ids,
                                           validation_id=validation_id,
                                           status=status,
                                           docker_image=validator_docker_image,
                                           original_validation_id=orig_val_id)
        validation_event.create_record()
        return validation_event

    def _update_validation_event(self, validator_docker_image, validation_id, orig_val_id, status="SCHEDULED"):
        validation_event = ValidationEvent(file_ids=self.file_db_ids,
                                           validation_id=validation_id,
                                           job_id=self.batch_job_id,
                                           status=status,
                                           docker_image=validator_docker_image,
                                           original_validation_id=orig_val_id)
        validation_event.update_record()
        return validation_event

    def _find_or_create_job_definition_for_image(self, validator_docker_image):
        job_defn = JobDefinition(docker_image=validator_docker_image, deployment=os.environ['DEPLOYMENT_STAGE'])
        if job_defn.load():
            return job_defn
        else:
            job_defn.create(job_role_arn=self.config.validation_job_role_arn)
        return job_defn

    @retry_on_aws_too_many_requests
    def _enqueue_batch_job(self, job_defn, command, environment, validation_id):
        job_name = "-".join(["validation", os.environ['DEPLOYMENT_STAGE'], self.upload_area_uuid, validation_id])
        job_name = re.sub(self.JOB_NAME_ALLOWABLE_CHARS, "", job_name)[0:128]
        job = batch.submit_job(
            jobName=job_name,
            jobQueue=self.config.validation_job_q_arn,
            jobDefinition=job_defn.arn,
            containerOverrides={
                'command': command,
                'environment': [dict(name=k, value=v) for k, v in environment.items()]
            }
        )
        print(f"Enqueued job {job['jobId']} to validate {self.file_keys} "
              f"using job definition {job_defn.arn}:")
        print(json.dumps(job))
        return job['jobId']
