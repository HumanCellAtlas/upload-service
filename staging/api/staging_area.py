import json, base64
from functools import reduce

import boto3
from botocore.exceptions import ClientError

from . import StagingException

s3 = boto3.resource('s3')
iam = boto3.resource('iam')


class StagingArea:

    STAGING_BUCKET_NAME_PREFIX = 'org-humancellatlas-staging-'
    STAGING_USER_NAME_PREFIX = 'staging-user-'
    STAGING_ACCESS_POLICY_PREFIX = 'staging-'
    CHECKSUM_TAGS = ('hca-dss-sha1', 'hca-dss-sha256', 'hca-dss-crc32c', 'hca-dss-s3_etag')
    MIME_TAG = 'hca-dss-content-type'
    ALL_TAGS = CHECKSUM_TAGS + (MIME_TAG,)

    def __init__(self, uuid):
        self.uuid = uuid
        self.bucket_name = self.STAGING_BUCKET_NAME_PREFIX + uuid
        self.user_name = self.STAGING_USER_NAME_PREFIX + uuid
        self._bucket = s3.Bucket(self.bucket_name)
        self._user = iam.User(self.user_name)
        self._credentials = None

    def urn(self):
        encoded_credentials = base64.b64encode(json.dumps(self._credentials).encode('utf8')).decode('utf8')
        return f"hca:sta:aws:{self.uuid}:{encoded_credentials}"

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

    def ls(self):
        return {'files': self._file_list()}

    def lock(self):
        self._set_access_policy(rw_access=False)

    def unlock(self):
        self._set_access_policy(rw_access=True)

    def store_file(self, filename, content):
        self._bucket.Object(filename).put(Body=content)

    def is_extant(self) -> bool:
        try:
            self._bucket.load()
            return True
        except ClientError as e:
            if e.response['Error']['Code'] != '404':
                raise StagingException(status=500, title="Unexpected Error",
                                       detail=f"bucket.load() returned {e.response}")
            return False

    def _file_list(self):
        file_list = []
        paginator = s3.meta.client.get_paginator('list_objects')
        for page in paginator.paginate(Bucket=self.bucket_name):
            if 'Contents' in page:
                for o in page['Contents']:
                    tagging = s3.meta.client.get_object_tagging(Bucket=self.bucket_name, Key=o['Key'])
                    file_info = {'name': o['Key'], 'size': o['Size']}
                    if 'TagSet' in tagging:
                        tags = self._decode_tags(tagging['TagSet'])
                        for tag in self.ALL_TAGS:
                            if tag in tags:
                                file_info[tag[8:]] = tags[tag]  # 8: = cut off hca-dss-
                    file_list.append(file_info)
        return file_list

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

    @staticmethod
    def _decode_tags(tags: list) -> dict:
        if not tags:
            return {}
        simplified_dicts = list({tag['Key']: tag['Value']} for tag in tags)
        return reduce(lambda x, y: dict(x, **y), simplified_dicts)


class GcpStagingArea(StagingArea):

    STAGING_ACCESS_POLICY_PREFIX = 'staging-'

    def __init__(self, uuid):
        super().__init__(uuid)
        raise NotImplementedError()
