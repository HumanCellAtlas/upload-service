#!/usr/bin/env python3.6
"""
Manage Upload Service AWS Batch Infrastructure
"""

import argparse
import hashlib
import sys
import time

import boto3

ec2r = boto3.resource('ec2')
batch = boto3.client('batch')
# ecr = boto3.client('ecr')


class JobQueue:

    def __init__(self, name=None, arn=None, metadata=None):
        if not name and not metadata:
            raise RuntimeError("you must provide name or metadata")
        self.metadata = metadata
        self.name = name if name else metadata['jobQueueName']
        if not arn:
            if metadata:
                self.arn = metadata['jobQueueArn']
        print(f"Job Queue {name}:")

    def find_or_create(self, compute_env_arn):
        if self.load():
            print(f"\tfound {self.arn}")
        else:
            self.create(compute_env_arn)
        return self

    def load(self):
        jobqs = batch.describe_job_queues(jobQueues=[self.name])['jobQueues']
        if len(jobqs) > 0:
            self.metadata = jobqs[0]
            self.arn = self.metadata['jobQueueArn']
            return self
        else:
            return None

    def create(self, compute_env_arn):
        self.metadata = batch.create_job_queue(
            jobQueueName=self.name,
            state='ENABLED',
            priority=1,
            computeEnvironmentOrder=[
                {
                    'order': 1,
                    'computeEnvironment': compute_env_arn
                },
            ]
        )
        self.arn = self.metadata['jobQueueArn']
        print(f"\tcreated {self.arn}")

    def disable(self):
        if self.metadata['state'] != 'DISABLED':
            batch.update_job_queue(jobQueue=self.arn, state='DISABLED')
        while True:
            time.sleep(1)
            self.load()
            if not self.metadata['status'] == 'UPDATING':
                break

    def delete(self):
        if self.load():
            print(f"Deleting job queue {self.name}...")
            self.disable()
            batch.delete_job_queue(jobQueue=self.arn)
            while self.load():
                time.sleep(1)


class ComputeEnvironment:

    SECURITY_GROUPS = ["default",
                       "inbound-ssh-from-hca-teams"]

    def __init__(self, name=None, arn=None, metadata=None):
        if not name and not metadata:
            raise RuntimeError("you must provide name or metadata")
        self.metadata = metadata
        self.name = name if name else metadata['computeEnvironmentName']
        if not arn:
            if metadata:
                self.arn = metadata['computeEnvironmentArn']
        print(f"Compute environment {self.name}:")

    def find_or_create(self, ami, account_id, vpc, ec2_key_pair):
        if self.load():
            print(f"\tfound {self.arn}")
        else:
            self.create(ami, account_id, vpc, ec2_key_pair)
        return self

    def load(self):
        compenvs = batch.describe_compute_environments(computeEnvironments=[self.name])['computeEnvironments']
        if len(compenvs) > 0:
            self.metadata = compenvs[0]
            self.arn = self.metadata['computeEnvironmentArn']
            return self
        else:
            return None

    def create(self, ami, account_id, vpc, ec2_key_pair):
        self.metadata = batch.create_compute_environment(
            computeEnvironmentName=self.name,
            type='MANAGED',
            state='ENABLED',
            computeResources={
                'type': 'EC2',  # TODO: 'SPOT'?
                'minvCpus': 0,
                'maxvCpus': 64,
                'desiredvCpus': 0,
                'instanceTypes': ['m4'],
                'imageId': ami.id,
                'subnets': [subnet.id for subnet in vpc.subnets.all()],
                'securityGroupIds': [sg.id for sg in vpc.security_groups.filter(GroupNames=self.SECURITY_GROUPS)],
                'ec2KeyPair': ec2_key_pair,
                'instanceRole': f'arn:aws:iam::{account_id}:instance-profile/ecsInstanceRole',
                'tags': {
                    'Name': self.name
                },
                # 'bidPercentage': 123,
                # 'spotIamFleetRole': 'string'
            },
            serviceRole=f'arn:aws:iam::{account_id}:role/service-role/AWSBatchServiceRole'
        )
        self.arn = self.metadata['computeEnvironmentArn']
        self._wait_til_it_settles()
        print(f"\tcreated {self.arn}")

    def disable(self):
        if self.metadata['state'] != 'DISABLED':
            batch.update_compute_environment(computeEnvironment=self.arn, state='DISABLED')
            time.sleep(1)
        self._wait_til_it_settles()

    def delete(self):
        if self.load():
            print(f"Deleting compute environment {self.name}...")
            self.disable()
            batch.delete_compute_environment(computeEnvironment=self.arn)
            while self.load():
                time.sleep(1)

    def _wait_til_it_settles(self):
        self.load()
        while self.metadata['status'] != 'VALID':
            time.sleep(1)
            self.load()


class JobDefinition:

    @classmethod
    def clear_all(cls):
        for jobdef in batch.describe_job_definitions(status='ACTIVE')['jobDefinitions']:
            cls(metadata=jobdef).delete()

    def __init__(self, docker_image=None, arn=None, metadata=None):
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
        jobdefs = batch.describe_job_definitions(jobDefinitionName=self.name, status='ACTIVE')['jobDefinitions']
        if len(jobdefs) > 0:
            self.metadata = jobdefs[0]
            self.arn = self.metadata['jobDefinitionArn']
            return self
        else:
            return None

    def create(self, job_role_arn):
        self.metadata = batch.register_job_definition(
            jobDefinitionName=self.name,
            type='container',
            parameters={},
            containerProperties={
                'image': self.docker_image,
                'vcpus': 1,
                'memory': 1000,
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
        time.sleep(1)
        print(f"\tcreated {self.arn}")

    def delete(self):
        print(f"Deleting job definition {self.arn}")
        batch.deregister_job_definition(jobDefinition=self.arn)

    def _job_definition_name(self):
        """
        We create Job Definitions for each unique docker image we are given.
        As there is no way to search for job definitions wih a particular Docker image,
        we must put the Docker image name in the job definition name (the only thing we can search on).
        We hash the image name as it will contain characters that aren't allowed in a job definition name.
        """
        hasher = hashlib.sha1()
        hasher.update(bytes(self.docker_image, 'utf8'))
        return f"upload-validator-{hasher.hexdigest()}"


class ValidationBatchSetupBuilder:

    def __init__(self, deployment):
        self.deployment = deployment
        self.comp_env_name = f"dcp-upload-{self.deployment}"
        self.job_queue_name = f"dcp-upload-queue-{self.deployment}"
        self.account_id = boto3.client('sts').get_caller_identity().get('Account')

    def setup_batch_infrastructure(self, ami_name_or_id, ec2_key_pair):
        vpc = self._find_vpc()  # needed for subnet ids and security groups
        ami = self._find_ami(self.account_id, ami_name_or_id)
        cenv = ComputeEnvironment(name=self.comp_env_name).find_or_create(ami, self.account_id, vpc, ec2_key_pair)
        JobQueue(self.job_queue_name).find_or_create(cenv.arn)

    def teardown_batch_infrastructure(self):
        JobQueue(self.job_queue_name).delete()
        ComputeEnvironment(self.comp_env_name).delete()

    def test_batch_infrastructure(self, docker_image, command):
        job_role_arn = f'arn:aws:iam::{self.account_id}:role/upload-validator-{self.deployment}'
        job_defn = JobDefinition(docker_image).find_or_create(job_role_arn)
        jobq = JobQueue(self.job_queue_name).load()
        self._submit_test_job(job_defn.arn, jobq.arn, command)

    def clear_job_definitions(self):
        JobDefinition.clear_all()

    def _find_vpc(self):
        vpcs = list(ec2r.vpcs.all())
        if len(vpcs) == 0:
            raise RuntimeError("No VPCs!")
        elif len(vpcs) > 1:
            sys.stderr.write("There is more than one VPC now.  "
                             "This program needs to be enhanced to allow you to pick one.\n")
            exit(1)
        vpc = vpcs[0]
        print(f"Using VPC {vpc.id}")
        return vpc

    def _find_ami(self, account_id, ami_name_or_id):
        images = list(ec2r.images.filter(Owners=[account_id], ImageIds=[ami_name_or_id]))
        if len(images) == 0:
            images = list(ec2r.images.filter(Owners=[account_id],
                                             Filters=[{'Name': 'name', 'Values': [ami_name_or_id]}]))
        if len(images) == 0:
            raise RuntimeError(f"Cannot find AMI with name or ID {ami_name_or_id}")
        ami = images[0]
        print(f"Found AMI {ami.id}: {ami.name}")
        return ami

    def _submit_test_job(self, jobdefn_arn, jobq_arn, command):
        response = batch.submit_job(
            jobName='spierson-test-job',
            jobQueue=jobq_arn,
            jobDefinition=jobdefn_arn,
            containerOverrides={
                'command': command
            }
        )
        print(response)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('deployment', choices=['dev', 'integration', 'staging', 'prod'], help="deployment")
    subparsers = parser.add_subparsers(help="action")

    build_parser = subparsers.add_parser("setup")
    build_parser.set_defaults(command='setup')
    build_parser.add_argument('ami', metavar="AMI", help="Use this AMI (ID or name) when building compute environment")
    build_parser.add_argument('key_pair', metavar="KEY_PAIR",
                              help="Use this EC2 key pair when building compute environment")

    build_parser = subparsers.add_parser("teardown")
    build_parser.set_defaults(command='teardown')

    test_parser = subparsers.add_parser("test")
    test_parser.set_defaults(command='test')
    test_parser.add_argument("image", metavar="IMAGE", help="Test Batch setup with this Docker image")
    test_parser.add_argument("test_command", nargs=argparse.REMAINDER, help="Command and arguments for Docker image")

    clear_parser = subparsers.add_parser("clear")
    clear_parser.set_defaults(command='clear')
    clear_parser.add_argument("clear_what", metavar="WHAT", choices=['job-defns'],
                              help="Clear out entities of this type.")

    args = parser.parse_args()

    builder = ValidationBatchSetupBuilder(args.deployment)

    if args.command == 'setup':
        builder.setup_batch_infrastructure(args.ami, args.key_pair)
    elif args.command == 'teardown':
        builder.teardown_batch_infrastructure()
    elif args.command == 'test':
        builder.test_batch_infrastructure(docker_image=args.image, command=args.test_command)
    elif args.command == 'clear':
        if args.clear_what == 'job-defns':
            builder.clear_job_definitions()
