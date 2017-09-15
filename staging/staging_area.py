import json, base64, os

import boto3
from botocore.exceptions import ClientError

import staging

s3 = boto3.resource('s3')
iam = boto3.resource('iam')


class StagingArea:

    STAGING_BUCKET_NAME = os.environ['STAGING_S3_BUCKET']
    STAGING_USER_NAME_PREFIX = f"staging-{os.environ['DEPLOYMENT_STAGE']}-user-"
    STAGING_ACCESS_POLICY_PREFIX = 'staging-'

    def __init__(self, uuid):
        self.uuid = uuid
        self.key_prefix = f"{self.uuid}/"
        self.key_prefix_length = len(self.key_prefix)
        self.bucket_name = self.STAGING_BUCKET_NAME
        self.user_name = self.STAGING_USER_NAME_PREFIX + uuid
        self._bucket = s3.Bucket(self.bucket_name)
        self._user = iam.User(self.user_name)
        self._credentials = None

    def urn(self):
        encoded_credentials = base64.b64encode(json.dumps(self._credentials).encode('utf8')).decode('utf8')
        return f"hca:sta:aws:{self.uuid}:{encoded_credentials}"

    def create(self):
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
        self._empty_staging_area()

    def ls(self):
        return {'files': self._file_list()}

    def lock(self):
        policy_name = self.STAGING_ACCESS_POLICY_PREFIX + self.uuid
        iam.UserPolicy(self.user_name, policy_name).delete()

    def unlock(self):
        self._set_access_policy()

    def store_file(self, filename, content, content_type):
        key = f"{self.uuid}/{filename}"
        s3obj = self._bucket.Object(key)
        s3obj.put(Body=content, ContentType=content_type)
        file = staging.StagedFile(staging_area=self, s3object=s3obj)
        file.compute_checksums()
        file.save_tags()
        return file.info()

    def staged_file(self, filename):
        key = f"{self.uuid}/{filename}"
        return staging.StagedFile.from_s3_key(self, key)

    def is_extant(self) -> bool:
        # A staging area is a folder, however there is no concept of folder in S3.
        # The existence of a staging area is the existence of the user who can access that area.
        try:
            self._user.load()
            return True
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchEntity':
                raise staging.StagingException(status=500, title="Unexpected Error",
                                               detail=f"bucket.load() returned {e.response}")
            return False

    def _file_list(self):
        file_list = []
        paginator = s3.meta.client.get_paginator('list_objects')
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.key_prefix):
            if 'Contents' in page:
                for o in page['Contents']:
                    file = staging.StagedFile.from_s3_key(self, o['Key'])
                    file_list.append(file.info())
        return file_list

    def _set_access_policy(self):
        policy_name = self.STAGING_ACCESS_POLICY_PREFIX + self.uuid
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:PutObject",
                        "s3:PutObjectTagging"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{self.bucket_name}/{self.uuid}/*",
                    ]
                }
            ]
        }
        self._user.create_policy(PolicyName=policy_name, PolicyDocument=json.dumps(policy_document))

    def _create_credentials(self):
        credentials = self._user.create_access_key_pair()
        self._credentials = {'AWS_ACCESS_KEY_ID': credentials.access_key_id,
                             'AWS_SECRET_ACCESS_KEY': credentials.secret_access_key}

    def _empty_staging_area(self):
        paginator = s3.meta.client.get_paginator('list_objects')
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.uuid):
            if 'Contents' in page:
                for o in page['Contents']:
                    s3.meta.client.delete_object(Bucket=self.bucket_name, Key=o['Key'])
