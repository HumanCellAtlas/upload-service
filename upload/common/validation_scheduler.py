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

    def __init__(self, uploaded_file: UploadedFile):
        self.file = uploaded_file
        self.file_key = self.file.upload_area.uuid + '/' + urllib.parse.unquote(self.file.name)
        self.config = UploadConfig()

    def check_file_can_be_validated(self):
        return self.file.size < MAX_FILE_SIZE_IN_BYTES

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
    def add_to_validation_sqs(self, filename: str, validator_image: str, env: dict, orig_val_id=None):
        validation_id = str(uuid.uuid4())
        payload = {
            'upload_area_uuid': self.file.upload_area.uuid,
            'filename': filename,
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
                                  detail=f"Adding file {self.file_key} was unsuccessful to \
                                          so pre batch sqs {self.config.area_deletion_q_url} )")
        logger.info(f"added file {self.file_key} to pre batch sqs")
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
        url_safe_file_key = urllib.parse.quote(self.file_key)
        file_s3loc = "s3://{bucket}/{file_key}".format(
            bucket=self.file.upload_area.bucket_name,
            file_key=url_safe_file_key
        )
        command = ['/validator', file_s3loc]
        logger.info(f"scheduling batch job with {env}")
        self.batch_job_id = self._enqueue_batch_job(job_defn, command, env)
        self._update_validation_event(docker_image, validation_id, orig_val_id)
        return validation_id

    def _create_validation_event(self, validator_docker_image, validation_id, orig_val_id, status="SCHEDULING_QUEUED"):
        validation_event = ValidationEvent(file_id=self.file.db_id,
                                           validation_id=validation_id,
                                           status=status,
                                           docker_image=validator_docker_image,
                                           original_validation_id=orig_val_id)
        validation_event.create_record()
        return validation_event

    def _update_validation_event(self, validator_docker_image, validation_id, orig_val_id, status="SCHEDULED"):
        validation_event = ValidationEvent(file_id=self.file.db_id,
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
    def _enqueue_batch_job(self, job_defn, command, environment):
        job_name = "-".join(["validation", os.environ['DEPLOYMENT_STAGE'], self.file.upload_area.uuid, self.file.name])
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
        print(f"Enqueued job {job['jobId']} to validate {self.file.upload_area.uuid}/{self.file.name} "
              f"using job definition {job_defn.arn}:")
        print(json.dumps(job))
        return job['jobId']
