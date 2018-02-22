import os

import boto3

from upload.common.batch import JobDefinition


class TestBatch:

    DEFAULT_QUEUE = f"dcp-upload-validation-q-{os.environ['DEPLOYMENT_STAGE']}"
    DEFAULT_ROLE = f"dcp-upload-validation-job-{os.environ['DEPLOYMENT_STAGE']}"

    def __init__(self, queue_name, role_name):
        self.queue_name = queue_name
        self.role_name = role_name

    def run(self, docker_image, command, env=None):

        batch = boto3.client('batch')
        account_id = boto3.client('sts').get_caller_identity().get('Account')

        job_queue_arn = f"arn:aws:batch:us-east-1:{account_id}:job-queue/{self.queue_name}"
        job_role_arn = f"arn:aws:iam::{account_id}:role/{self.role_name}"
        print(f"SAM: role_name={self.role_name}")
        print(f"SAM: job_role_arn={job_role_arn}")

        job_defn = JobDefinition(
            docker_image=docker_image,
            deployment=os.environ['DEPLOYMENT_STAGE']
        ).find_or_create(job_role_arn)

        response = batch.submit_job(
            jobName='test-job',
            jobQueue=job_queue_arn,
            jobDefinition=job_defn.arn,
            containerOverrides={
                'command': command,
                'environment': self._environment(env)
            }
        )
        print(f"Submit job returned {response}")

    @staticmethod
    def _environment(env_list):
        # Split ["A=1", "B=2"] into [["A", "1"], ["B", "2"]]
        split_vars = map(lambda x: x.split('='), env_list or [])
        # Return [{"A": "1"}, {"B": "2"}]
        return [dict(name=kv[0], value=kv[1]) for kv in split_vars]
