import json
import os
import re

import boto3

from . import UploadedFile
from .batch import JobDefinition

batch = boto3.client('batch')


class Validation:

    JOB_NAME_ALLOWABLE_CHARS = '[^\w-]'

    def __init__(self, uploaded_file: UploadedFile):
        self.file = uploaded_file

    def schedule_validation(self, validator_docker_image: str, environment: dict) -> str:
        job_defn = self._find_or_create_job_definition_for_image(validator_docker_image)
        environment['DEPLOYMENT_STAGE'] = os.environ['DEPLOYMENT_STAGE']
        file_s3loc = "s3://{bucket}/{upload_area}/{filename}".format(
            bucket=self.file.upload_area.bucket_name,
            upload_area=self.file.upload_area.uuid,
            filename=self.file.name
        )
        command = ['/validator', file_s3loc]
        validation_id = self._enqueue_batch_job(job_defn, command, environment)
        return validation_id

    def _find_or_create_job_definition_for_image(self, validator_docker_image):
        job_defn = JobDefinition(docker_image=validator_docker_image, deployment=os.environ['DEPLOYMENT_STAGE'])
        if job_defn.load():
            return job_defn
        else:
            job_defn.create(job_role_arn=os.environ['VALIDATION_JOB_ROLE_ARN'])
        return job_defn

    def _enqueue_batch_job(self, job_defn, command, environment):
        job_name = "-".join(["validation", os.environ['DEPLOYMENT_STAGE'], self.file.upload_area.uuid, self.file.name])
        job_name = re.sub(self.JOB_NAME_ALLOWABLE_CHARS, "", job_name)[0:128]
        job = batch.submit_job(
            jobName=job_name,
            jobQueue=os.environ['VALIDATION_JOB_QUEUE_ARN'],
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
