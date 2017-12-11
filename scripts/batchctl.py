#!/usr/bin/env python3.6
"""
Manage Upload Service AWS Batch Infrastructure
"""

import argparse
import json
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from upload.batch import JobDefinition

ec2r = boto3.resource('ec2')
batch = boto3.client('batch')
iam = boto3.client('iam')
account_id = boto3.client('sts').get_caller_identity().get('Account')


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


class BatchJobPolicyAndRole:

    def __init__(self, deployment):
        self.deployment = deployment
        pass

    def setup(self):
        policy = self.find_or_create_policy()
        role = self.find_or_create_role()
        self.attach_policy_to_role(policy, role)

    def attach_policy_to_role(self, policy, role):
        policies = iam.list_attached_role_policies(RoleName=role['RoleName'])['AttachedPolicies']
        try:
            next((item for item in policies if item['PolicyArn'] == policy['Arn']))
            print(f"Policy {policy['PolicyName']} is attached to role {role['RoleName']}")
        except StopIteration:
            print(f"Attching policy {policy['PolicyName']} to role {role['RoleName']}")
            iam.attach_role_policy(RoleName=role['RoleName'], PolicyArn=policy['Arn'])

    def find_or_create_policy(self):
        policy_name = f"upload-batch-job-{self.deployment}"
        print(f"Policy {policy_name}:")
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
        try:
            policy = iam.get_policy(PolicyArn=policy_arn)['Policy']
            print(f"\t found {policy['Arn']}")
        except ClientError:
            policy = iam.create_policy(PolicyName=policy_name, PolicyDocument=self.policy_document())['Policy']
            print(f"\t created policy {policy['Arn']}")
        return policy

    def find_or_create_role(self):
        role_name = f"upload-batch-job-{self.deployment}"
        print(f"Role {role_name}:")
        try:
            role = iam.get_role(RoleName=role_name)['Role']
            print(f"\t found {role['Arn']}")
        except ClientError:
            role = iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=self.role_trust_document())['Role']
            print(f"\t created role {role['Arn']}")
        return role

    def teardown(self):
        self.delete_role()
        self.delete_policy()

    def delete_role(self):
        role_name = f"upload-batch-job-{self.deployment}"
        try:
            role = iam.get_role(RoleName=role_name)['Role']
        except ClientError:
            return
        for policy in iam.list_attached_role_policies(RoleName=role['RoleName'])['AttachedPolicies']:
            print(f"Detaching policy {policy['PolicyName']} from role {role['RoleName']}")
            iam.detach_role_policy(RoleName=role['RoleName'], PolicyArn=policy['PolicyArn'])
        print(f"Deleting {role['Arn']}")
        iam.delete_role(RoleName=role['RoleName'])

    def delete_policy(self):
        policy_name = f"upload-batch-job-{self.deployment}"
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
        try:
            policy = iam.get_policy(PolicyArn=policy_arn)['Policy']
        except ClientError:
            return
        for version in iam.list_policy_versions(PolicyArn=policy['Arn'])['Versions']:
            if not version['IsDefaultVersion']:
                print(f"Deleting policy version {policy['PolicyName']} version {version['VersionId']}")
                iam.delete_policy_version(PolicyArn=policy['Arn'], VersionId=version['VersionId'])
        print(f"Deleting {policy['Arn']}")
        iam.delete_policy(PolicyArn=policy['Arn'])

    def policy_document(self):
        return json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject"
                        ],
                        "Resource": [
                            f"arn:aws:s3:::org-humancellatlas-upload-{self.deployment}/*"
                        ]
                    }
                ]
            }
        )

    @staticmethod
    def role_trust_document():
        return json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "",
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "ecs-tasks.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
        )


class ValidationBatchSetupBuilder:

    def __init__(self, deployment):
        self.deployment = deployment
        self.comp_env_name = f"dcp-upload-{self.deployment}"
        self.job_queue_name = f"dcp-upload-queue-{self.deployment}"

    def setup_batch_infrastructure(self, ami_name_or_id, ec2_key_pair):
        vpc = self._find_vpc()  # needed for subnet ids and security groups
        ami = self._find_ami(ami_name_or_id)
        cenv = ComputeEnvironment(name=self.comp_env_name).find_or_create(ami, account_id, vpc, ec2_key_pair)
        JobQueue(self.job_queue_name).find_or_create(cenv.arn)
        BatchJobPolicyAndRole(self.deployment).setup()

    def teardown_batch_infrastructure(self):
        JobQueue(self.job_queue_name).delete()
        ComputeEnvironment(self.comp_env_name).delete()
        BatchJobPolicyAndRole(self.deployment).teardown()

    def test_batch_infrastructure(self, docker_image, command):
        job_role_arn = f'arn:aws:iam::{account_id}:role/upload-batch-job-{self.deployment}'
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

    def _find_ami(self, ami_name_or_id):
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
