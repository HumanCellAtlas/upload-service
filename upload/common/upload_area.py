import base64
import json
import os
import time
import boto3
import uuid
import pdb
from botocore.exceptions import ClientError

from dcplib.media_types import DcpMediaType

from .checksum import UploadedFileChecksummer
from .uploaded_file import UploadedFile
from .exceptions import UploadException
from .database import create_pg_record, update_pg_record
from .checksum_event import UploadedFileChecksumEvent

s3 = boto3.resource('s3')
iam = boto3.resource('iam')


class UploadArea:

    USER_NAME_TEMPLATE = "upload-{deployment_stage}-user-{uuid}"
    ACCESS_POLICY_NAME_TEMPLATE = "upload-{uuid}"
    IAM_SETTLE_TIME_SEC = 15

    def __init__(self, uuid):
        self.uuid = uuid
        self.key_prefix = f"{self.uuid}/"
        self.key_prefix_length = len(self.key_prefix)
        self.bucket_name = os.environ['BUCKET_NAME']
        self.user_name = self.USER_NAME_TEMPLATE.format(deployment_stage=self._deployment_stage, uuid=uuid)
        self._bucket = s3.Bucket(self.bucket_name)
        self._user = iam.User(self.user_name)
        self._credentials = None

    @property
    def _deployment_stage(self):
        return os.environ['DEPLOYMENT_STAGE']

    @property
    def urn(self):
        encoded_credentials = base64.b64encode(json.dumps(self._credentials).encode('utf8')).decode('utf8')
        if self._deployment_stage == 'prod':
            return f"dcp:upl:aws:{self.uuid}:{encoded_credentials}"
        else:
            return f"dcp:upl:aws:{self._deployment_stage}:{self.uuid}:{encoded_credentials}"

    @property
    def access_policy_name(self):
        return self.ACCESS_POLICY_NAME_TEMPLATE.format(uuid=self.uuid)

    def create(self):
        self.status = "CREATING"
        self._create_record()
        self._user.create()
        self._set_access_policy()
        self._create_credentials()
        time.sleep(self.IAM_SETTLE_TIME_SEC)
        self.status = "UNLOCKED"
        self._update_record()

    def delete(self):
        # This may need to be offloaded to an async lambda if _empty_bucket() starts taking a long time.
        self.status = "DELETING"
        self._update_record()
        self._empty_upload_area()
        for access_key in self._user.access_keys.all():
            access_key.delete()
        for policy in self._user.policies.all():
            policy.delete()
        self._user.delete()
        self.status = "DELETED"
        self._update_record()

    def ls(self):
        return {'files': self._file_list()}

    def lock(self):
        self.status = "LOCKING"
        self._update_record()
        iam.UserPolicy(self.user_name, self.access_policy_name).delete()
        time.sleep(self.IAM_SETTLE_TIME_SEC)
        self.status = "LOCKED"
        self._update_record()

    def unlock(self):
        self.status = "UNLOCKING"
        self._update_record()
        self._set_access_policy()
        time.sleep(self.IAM_SETTLE_TIME_SEC)
        self.status = "UNLOCKED"
        self._update_record()

    def store_file(self, filename, content, content_type):
        media_type = DcpMediaType.from_string(content_type)
        if 'dcp-type' not in media_type.parameters:
            raise UploadException(status=400, title="Invalid Content-Type",
                                  detail="Content-Type is missing parameter 'dcp-type'," +
                                         " e.g. 'application/json; dcp-type=\"metadata/sample\"'.")
        key = f"{self.uuid}/{filename}"
        s3obj = self._bucket.Object(key)
        s3obj.put(Body=content, ContentType=content_type)
        file = UploadedFile(upload_area=self, s3object=s3obj)
        file.fetch_or_create_db_record()
        checksummer = UploadedFileChecksummer(uploaded_file=file)
        checksum_id = str(uuid.uuid4())
        checksum_event = UploadedFileChecksumEvent(file_id=key,
                                                   checksum_id=checksum_id,
                                                   status="CHECKSUMMING")
        checksum_event.create_record()
        checksums = checksummer.checksum(report_progress=True)
        file.checksums = checksums
        file.save_tags()
        checksum_event.status = "CHECKSUMMED"
        checksum_event.checksums = checksums
        checksum_event.update_record()
        return file.info()

    def uploaded_file(self, filename):
        key = f"{self.uuid}/{filename}"
        return UploadedFile.from_s3_key(self, key)

    def is_extant(self) -> bool:
        # A upload area is a folder, however there is no concept of folder in S3.
        # The existence of a upload area is the existence of the user who can access that area.
        try:
            self._user.load()
            return True
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchEntity':
                raise UploadException(status=500, title="Unexpected Error",
                                      detail=f"bucket.load() returned {e.response}")
            return False

    def _file_list(self):
        file_list = []
        paginator = s3.meta.client.get_paginator('list_objects')
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.key_prefix):
            if 'Contents' in page:
                for o in page['Contents']:
                    file = UploadedFile.from_s3_key(self, o['Key'])
                    file_list.append(file.info())
        return file_list

    def _set_access_policy(self):
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
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:ListBucket"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{self.bucket_name}"
                    ],
                    "Condition": {
                        "StringEquals": {
                            "s3:prefix": f"{self.uuid}/"
                        }
                    }
                }
            ]
        }
        self._user.create_policy(PolicyName=self.access_policy_name, PolicyDocument=json.dumps(policy_document))

    def _create_credentials(self):
        credentials = self._user.create_access_key_pair()
        self._credentials = {'AWS_ACCESS_KEY_ID': credentials.access_key_id,
                             'AWS_SECRET_ACCESS_KEY': credentials.secret_access_key}

    def _empty_upload_area(self):
        paginator = s3.meta.client.get_paginator('list_objects')
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.uuid):
            if 'Contents' in page:
                for o in page['Contents']:
                    s3.meta.client.delete_object(Bucket=self.bucket_name, Key=o['Key'])

    def _format_prop_vals_dict(self):
        return {
            "id": self.uuid,
            "bucket_name": self.bucket_name,
            "status": self.status
        }

    def _create_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        create_pg_record("upload_area", prop_vals_dict)

    def _update_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        update_pg_record("upload_area", prop_vals_dict)
