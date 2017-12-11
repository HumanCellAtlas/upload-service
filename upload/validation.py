import json
import os
import re

import boto3

from . import UploadedFile
from .batch import JobDefinition

batch = boto3.client('batch')


class Validation:

    JOB_QUEUE_NAME_TEMPLATE = "dcp-upload-queue-{deployment_stage}"
    JOB_ROLE_ARN_TEMPLATE = 'arn:aws:iam::{account_id}:role/upload-batch-job-{stage}'
    JOB_NAME_ALLOWABLE_CHARS = '[^\w-]'

    def __init__(self, uploaded_file: UploadedFile):
        self.file = uploaded_file

    def schedule_validation(self, validator_docker_image: str, environment: dict) -> str:
        job_defn = self._find_or_create_job_definition_for_image(validator_docker_image)
        job_q_arn = self._find_job_queue()
        environment['DEPLOYMENT_STAGE'] = os.environ['DEPLOYMENT_STAGE']
        file_s3loc = "s3://{bucket}/{upload_area}/{filename}".format(
            bucket=self.file.upload_area.bucket_name,
            upload_area=self.file.upload_area.uuid,
            filename=self.file.name
        )
        command = ['/validator', file_s3loc]
        validation_id = self._enqueue_batch_job(job_q_arn, job_defn, command, environment)
        return validation_id

    def _find_or_create_job_definition_for_image(self, validator_docker_image):
        job_defn = JobDefinition(docker_image=validator_docker_image, deployment=os.environ['DEPLOYMENT_STAGE'])
        if job_defn.load():
            return job_defn
        else:
            job_role_arn = self.JOB_ROLE_ARN_TEMPLATE.format(
                account_id=boto3.client('sts').get_caller_identity().get('Account'),
                stage=os.environ['DEPLOYMENT_STAGE']
            )
            job_defn.create(job_role_arn=job_role_arn)
        return job_defn

    def _find_job_queue(self):
        validation_queue_name = self.JOB_QUEUE_NAME_TEMPLATE.format(deployment_stage=os.environ['DEPLOYMENT_STAGE'])
        jobqs = batch.describe_job_queues(jobQueues=[validation_queue_name])['jobQueues']
        assert len(jobqs) == 1, f"Expected 1 job queue named {validation_queue_name}, found {len(jobqs)}"
        return jobqs[0]['jobQueueArn']

    def _enqueue_batch_job(self, job_q_arn, job_defn, command, environment):
        job_name = "-".join(["validation", os.environ['DEPLOYMENT_STAGE'], self.file.upload_area.uuid, self.file.name])
        job_name = re.sub(self.JOB_NAME_ALLOWABLE_CHARS, "", job_name)[0:128]
        job = batch.submit_job(
            jobName=job_name,
            jobQueue=job_q_arn,
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
