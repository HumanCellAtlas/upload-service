import json
import hashlib
import os
import uuid

import boto3

from . import UploadedFile


class Validation:

    JOB_QUEUE_NAME_TEMPLATE = "dcp-upload-queue-{deployment_stage}"

    def __init__(self, uploaded_file: UploadedFile):
        self.file = uploaded_file
        self.validation_id = str(uuid.uuid4())
        self.batch = boto3.client('batch')

    def schedule_validation(self, validator_docker_image: str, environment: dict) -> str:
        jobdefn_arn = self._find_or_create_job_definition_for_image(validator_docker_image)
        job_q_arn = self._find_job_queue()
        environment['VALIDATION_ID'] = self.validation_id
        environment['DEPLOYMENT_STAGE'] = os.environ['DEPLOYMENT_STAGE']
        file_s3loc = "s3://{bucket}/{upload_area}/{filename}".format(
            bucket=self.file.upload_area.bucket_name,
            upload_area=self.file.upload_area.uuid,
            filename=self.file.name
        )
        command = ['/validator', file_s3loc]
        self._enqueue_batch_job(job_q_arn, jobdefn_arn, command, environment)
        return self.validation_id

    def _find_or_create_job_definition_for_image(self, validator_docker_image):
        jobdefn_name = self._job_definition_name(validator_docker_image)
        jobdefn_arn = self._find_job_definition(jobdefn_name)
        if jobdefn_arn:
            print(f"Found existing Job Definition for image {validator_docker_image}: {jobdefn_arn}")
            return jobdefn_arn
        else:
            job_role_arn = 'arn:aws:iam::{account_id}:role/upload-validator-{stage}'.format(
                account_id=boto3.client('sts').get_caller_identity().get('Account'),
                stage=os.environ['DEPLOYMENT_STAGE']
            )
            jobdefn = self.batch.register_job_definition(
                jobDefinitionName=jobdefn_name,
                type='container',
                parameters={},
                containerProperties={
                    'image': validator_docker_image,
                    'vcpus': 2,
                    'memory': 2000,
                    'command': [],
                    'jobRoleArn': job_role_arn,
                    'volumes': [
                        {
                            'host': {'sourcePath': '/data'},
                            'name': 'data'
                        },
                    ],
                    'mountPoints': [
                        {
                            'containerPath': '/data',
                            'readOnly': False,
                            'sourceVolume': 'data'
                        },
                    ],
                },
                retryStrategy={
                    'attempts': 1
                }
            )
            print(f"Created Job Definition for image {validator_docker_image}: {jobdefn_arn}:")
            print(json.dumps(jobdefn, indent=4))
            return jobdefn['jobDefinitionArn']

    @staticmethod
    def _job_definition_name(validator_docker_image):
        """
        We create Job Definitions for each unique validator image we are given.
        As there is no way to search for job definitions wih a particular Docker image,
        we must put the Docker image name in the job definition name (the only think we can search on).
        We hash the image name as it will contain characters that aren't allowed in a job definition name.
        """
        hasher = hashlib.sha1()
        hasher.update(bytes(validator_docker_image, 'utf8'))
        return f"upload-validator-{hasher.hexdigest()}"

    def _find_job_definition(self, job_definition_name):
        response = self.batch.describe_job_definitions(jobDefinitionName=job_definition_name, status='ACTIVE')
        jobdefns = response['jobDefinitions']
        if len(jobdefns) > 0:
            return jobdefns[0]['jobDefinitionArn']
        else:
            return None

    def _find_job_queue(self):
        validation_queue_name = self.JOB_QUEUE_NAME_TEMPLATE.format(deployment_stage=os.environ['DEPLOYMENT_STAGE'])
        jobqs = self.batch.describe_job_queues(jobQueues=[validation_queue_name])['jobQueues']
        assert len(jobqs) == 1, f"Expected 1 job queue named {validation_queue_name}, found {len(jobqs)}"
        return jobqs[0]['jobQueueArn']

    def _enqueue_batch_job(self, job_q_arn, jobdefn_arn, command, environment):
        job = self.batch.submit_job(
            jobName=f"validation-{self.validation_id}",
            jobQueue=job_q_arn,
            jobDefinition=jobdefn_arn,
            containerOverrides={
                'command': command,
                'environment': [dict(name=k, value=v) for k, v in environment.items()]
            }
        )
        print(f"Enqueued job {job['jobId']} to validate {self.file.upload_area.uuid}/{self.file.name} "
              f"using job definition {jobdefn_arn}:")
        print(json.dumps(job, indent=4))
