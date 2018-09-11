import hashlib
import json
import os

import boto3

from .retry import retry_on_aws_too_many_requests

batch = boto3.client('batch')


class JobDefinition:

    @classmethod
    def clear_all(cls):
        deleted_count = 0
        for jobdef in batch.describe_job_definitions(status='ACTIVE')['jobDefinitions']:
            cls(metadata=jobdef).delete()
            deleted_count += 1
        return deleted_count

    def __init__(self, docker_image=None, deployment=None, arn=None, metadata=None):
        self.deployment = deployment if deployment else os.environ['DEPLOYMENT_STAGE']
        if not docker_image and not metadata:
            raise RuntimeError("you must provide docker_image or metadata")
        self.metadata = metadata
        self.docker_image = docker_image if docker_image else metadata['containerProperties']['image']
        self.name = self._job_definition_name() if docker_image else metadata['jobDefinitionName']
        if not arn:
            if metadata:
                self.arn = metadata['jobDefinitionArn']
        print(f"Job definition {self.name} for {self.docker_image}:")

    def find_or_create(self, job_role_arn):
        if self.load():
            print(f"\tfound {self.arn}")
        else:
            self.create(job_role_arn)
        return self

    def load(self):
        jobdefs = self._describe_job_definitions(jobDefinitionName=self.name, status='ACTIVE')['jobDefinitions']
        if len(jobdefs) > 0:
            self.metadata = jobdefs[0]
            self.arn = self.metadata['jobDefinitionArn']
            return self
        else:
            return None

    @retry_on_aws_too_many_requests
    def create(self, job_role_arn):
        self.metadata = batch.register_job_definition(
            jobDefinitionName=self.name,
            type='container',
            parameters={},
            containerProperties={
                'image': self.docker_image,
                'vcpus': 2,
                'memory': 2048,
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
                ]
            },
            retryStrategy={
                'attempts': 1
            }
        )
        self.arn = self.metadata['jobDefinitionArn']
        print(f"\tcreated {self.arn}")
        print(json.dumps(self.metadata, indent=4))

    def delete(self):
        print(f"Deleting job definition {self.name} ({self.docker_image})")
        batch.deregister_job_definition(jobDefinition=self.arn)

    @retry_on_aws_too_many_requests
    def _describe_job_definitions(self, *args, **kwargs):
        return batch.describe_job_definitions(*args, **kwargs)

    def _job_definition_name(self):
        """
        We create Job Definitions for each unique docker image we are given.
        As there is no way to search for job definitions wih a particular Docker image,
        we must put the Docker image name in the job definition name (the only thing we can search on).
        We hash the image name as it will contain characters that aren't allowed in a job definition name.
        """
        hasher = hashlib.sha1()
        hasher.update(bytes(self.docker_image, 'utf8'))
        return f"upload-{self.deployment}-{hasher.hexdigest()}"
