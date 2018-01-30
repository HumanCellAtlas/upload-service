import sys
import time

import boto3

from ..component import Component


class ComputeEnvironment(Component):
    def __init__(self, name, **options):
        self.name = name
        self.options = options
        self.metadata = None
        super().__init__(**options)
        self.batch = boto3.client('batch')

    def __str__(self):
        return f"Compute environment {self.name}"

    @property
    def arn(self):
        return self.metadata['computeEnvironmentArn'] if self.metadata else None

    def is_setup(self):
        self._load()
        return self.metadata is not None

    def set_it_up(self):
        if not self.options.get('ami'):
            raise RuntimeError("You must provide option --ami to setup the Batch Compute Environment")
        if not self.options.get('ec2_key_pair'):
            raise RuntimeError("You must provide option --ec2-key-pair to setup the Batch Compute Environment")
        security_groups = self.options['security_groups'].split(",")

        vpc = self._find_vpc()
        account_id = boto3.client('sts').get_caller_identity().get('Account')
        security_group_ids = [sg.id for sg in vpc.security_groups.all() if sg.group_name in security_groups]

        self.metadata = self.batch.create_compute_environment(
            computeEnvironmentName=self.name,
            type='MANAGED',
            state='ENABLED',
            computeResources={
                'type': 'EC2',  # TODO: 'SPOT'
                'minvCpus': 0,
                'maxvCpus': 64,
                'desiredvCpus': 0,
                'instanceTypes': ['m4'],
                'imageId': self.options['ami'],
                'subnets': [subnet.id for subnet in vpc.subnets.all()],
                'securityGroupIds': security_group_ids,
                'ec2KeyPair': self.options['ec2_key_pair'],
                'instanceRole': f'arn:aws:iam::{account_id}:instance-profile/ecsInstanceRole',
                'tags': {
                    'Name': self.name
                },
                # 'bidPercentage': 123,
                # 'spotIamFleetRole': 'string'
            },
            serviceRole=f'arn:aws:iam::{account_id}:role/service-role/AWSBatchServiceRole'
        )
        self._wait_til_it_settles()

    def tear_it_down(self):
        self._disable()
        self.batch.delete_compute_environment(computeEnvironment=self.arn)
        while self._load():
            time.sleep(1)

    def _load(self):
        compenvs = self.batch.describe_compute_environments(computeEnvironments=[self.name])['computeEnvironments']
        if len(compenvs) > 0:
            self.metadata = compenvs[0]
            return self
        else:
            self.metadata = None
            return None

    def _disable(self):
        if self.metadata['state'] != 'DISABLED':
            self.batch.update_compute_environment(computeEnvironment=self.arn, state='DISABLED')
            time.sleep(1)
        self._wait_til_it_settles()

    def _wait_til_it_settles(self):
        self._load()
        while self.metadata['status'] != 'VALID':
            time.sleep(1)
            self._load()

    def _find_vpc(self):
        vpcs = list(boto3.resource('ec2').vpcs.all())
        if len(vpcs) == 0:
            raise RuntimeError("No VPCs!")
        elif len(vpcs) > 1:
            sys.stderr.write("There is more than one VPC now.  "
                             "This program needs to be enhanced to allow you to pick one.\n")
            exit(1)
        vpc = vpcs[0]
        return vpc


class JobQueue(Component):

    def __init__(self, name=None, compute_env_arn=None, **options):
        self.name = name
        self.compute_env_arn = compute_env_arn
        self.metadata = None
        super().__init__(**options)
        self.batch = boto3.client('batch')

    def __str__(self):
        return f"Job queue {self.name}"

    @property
    def arn(self):
        return self.metadata['jobQueueArn'] if self.metadata else None

    def is_setup(self):
        self._load()
        return self.metadata is not None

    def set_it_up(self):
        self.metadata = self.batch.create_job_queue(
            jobQueueName=self.name,
            state='ENABLED',
            priority=1,
            computeEnvironmentOrder=[
                {'order': 1, 'computeEnvironment': self.compute_env_arn},
            ]
        )

    def tear_it_down(self):
        self._disable()
        self.batch.delete_job_queue(jobQueue=self.arn)
        while self._load():
            time.sleep(1)

    def _load(self):
        jobqs = self.batch.describe_job_queues(jobQueues=[self.name])['jobQueues']
        if len(jobqs) > 0:
            self.metadata = jobqs[0]
            return self
        else:
            self.metadata = None
            return None

    def _disable(self):
        if self.metadata['state'] != 'DISABLED':
            self.batch.update_job_queue(jobQueue=self.arn, state='DISABLED')
        while True:
            time.sleep(1)
            self._load()
            if not self.metadata['status'] == 'UPDATING':
                break

