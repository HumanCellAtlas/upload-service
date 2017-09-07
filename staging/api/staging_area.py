import json, base64

import boto3
from botocore.exceptions import ClientError

from . import StagingException

s3 = boto3.resource('s3')
iam = boto3.resource('iam')


class StagingArea:

    STAGING_BUCKET_NAME_PREFIX = 'org-humancellatlas-staging-'
    STAGING_USER_NAME_PREFIX = 'staging-user-'

    @classmethod
    def factory(cls, uuid, cloud):
        if cloud not in ('aws', 'gcp'):
            raise StagingException(400, title="Invalid 'cloud'", detail="cloud must be one of 'aws', 'gcp'")
        class_name = cloud.title() + 'StagingArea'
        return eval(class_name)(uuid)

    def __init__(self, uuid):
        self.uuid = uuid
        self.bucket_name = self.STAGING_BUCKET_NAME_PREFIX + uuid
        self.user_name = self.STAGING_USER_NAME_PREFIX + uuid
        self._credentials = None

    def urn(self):
        encoded_credentials = base64.b64encode(json.dumps(self._credentials).encode('utf8')).decode('utf8')
        return f"hca:sta:aws:{self.uuid}:{encoded_credentials}"


class AwsStagingArea(StagingArea):

    STAGING_ACCESS_POLICY_PREFIX = 'staging-'

    def __init__(self, uuid):
        super().__init__(uuid)
        self.cloud = 'aws'
        self._bucket = s3.Bucket(self.bucket_name)
        self._user = iam.User(self.user_name)

    def create(self):
        self._bucket.create()
        # self._enable_transfer_acceleration()
        self._user.create()
        self._set_access_policy()
        self._create_credentials()

    def delete(self):
        # This may need to be offloaded to an async lambda if _empty_bucket() starts taking a long time.
        for access_key in self._user.access_keys.all():
            access_key.delete()
        for policy in self._user.policies.all():
            policy.delete()
        self._user.delete()
        self._empty_bucket()
        self._bucket.delete()

    def lock(self):
        self._set_access_policy(rw_access=False)

    def unlock(self):
        self._set_access_policy(rw_access=True)

    def is_extant(self) -> bool:
        try:
            self._bucket.load()
            return True
        except ClientError as e:
            if e.response['Error']['Code'] != '404':
                raise StagingException(status=500, title="Unexpected Error",
                                       detail=f"bucket.load() returned {e.response}")
            return False

    def _enable_transfer_acceleration(self):
        s3.meta.client.put_bucket_accelerate_configuration(
            Bucket=self.bucket_name,
            AccelerateConfiguration={'Status': 'Enabled'}
        )

    def _set_access_policy(self, rw_access=True):
        policy_name = self.STAGING_ACCESS_POLICY_PREFIX + self.uuid
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:ListBucket"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{self.bucket_name}",
                        f"arn:aws:s3:::{self.bucket_name}/*",
                    ]
                }
            ]
        }
        if rw_access:
            policy_document['Statement'][0]['Action'].append("s3:PutObject")
        self._user.create_policy(PolicyName=policy_name, PolicyDocument=json.dumps(policy_document))

    def _create_credentials(self):
        credentials = self._user.create_access_key_pair()
        self._credentials = {'AWS_ACCESS_KEY_ID': credentials.access_key_id,
                             'AWS_SECRET_ACCESS_KEY': credentials.secret_access_key}

    def _empty_bucket(self):
        paginator = s3.meta.client.get_paginator('list_objects')
        for page in paginator.paginate(Bucket=self.bucket_name):
            if 'Contents' in page:
                for o in page['Contents']:
                    s3.meta.client.delete_object(Bucket=self.bucket_name, Key=o['Key'])


class GcpStagingArea(StagingArea):

    STAGING_ACCESS_POLICY_PREFIX = 'staging-'

    def __init__(self, uuid):
        super().__init__(uuid)
        raise NotImplementedError()
