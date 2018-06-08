import json
import os
import uuid

import boto3

from dcplib.media_types import DcpMediaType

from .checksum import UploadedFileChecksummer
from .uploaded_file import UploadedFile
from .checksum_event import UploadedFileChecksumEvent
from .exceptions import UploadException
from .upload_config import UploadConfig
from .logging import get_logger

if not os.environ.get("CONTAINER"):
    from .database import get_pg_record, create_pg_record, update_pg_record

logger = get_logger(__name__)

s3 = boto3.resource('s3')


class UploadArea:

    def __init__(self, uuid):
        self.uuid = uuid
        self.status = None
        self.config = UploadConfig()
        self.key_prefix = f"{self.uuid}/"
        self.key_prefix_length = len(self.key_prefix)
        self._bucket = s3.Bucket(self.bucket_name)

    @property
    def bucket_name(self):
        return self.config.bucket_name

    @property
    def _deployment_stage(self):
        return os.environ['DEPLOYMENT_STAGE']

    @property
    def uri(self):
        return f"s3://{self._bucket.name}/{self.key_prefix}"

    def create(self):
        self.status = "UNLOCKED"
        self._create_record()

    def credentials(self):
        record = self._db_record()
        if not record['status'] == 'UNLOCKED':
            raise UploadException(status=409, title="Upload Area is Not Writable",
                                  detail=f"Cannot issue credentials, upload area {self.uuid} is {record['status']}")

        sts = boto3.client("sts")
        policy_json = json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:PutObject", "s3:PutObjectTagging"],
                    "Resource": [f"arn:aws:s3:::{self.bucket_name}/{self.uuid}/*"]
                },
                {
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket"],
                    "Resource": [f"arn:aws:s3:::{self.bucket_name}"],
                    "Condition": {
                        "StringEquals": {"s3:prefix": f"{self.uuid}/"}
                    }
                }
            ]
        })
        logger.debug(policy_json)
        response = sts.assume_role(
            RoleArn=self.config.upload_submitter_role_arn,
            RoleSessionName=self.uuid,
            DurationSeconds=900,
            ExternalId="TBD",
            Policy=policy_json
        )
        creds = response['Credentials']
        del creds['Expiration']
        return creds

    def delete(self):
        # This may need to be offloaded to an async lambda if _empty_bucket() starts taking a long time.
        self.status = "DELETING"
        self._update_record()
        self._empty_upload_area()
        self.status = "DELETED"
        self._update_record()

    def ls(self):
        return {'files': self._file_list()}

    def lock(self):
        self.status = "LOCKED"
        self._update_record()

    def unlock(self):
        self.status = "UNLOCKED"
        self._update_record()

    def s3_object_for_file(self, filename):
        return self._bucket.Object(self.key_prefix + filename)

    def store_file(self, filename, content, content_type):
        media_type = DcpMediaType.from_string(content_type)
        if 'dcp-type' not in media_type.parameters:
            raise UploadException(status=400, title="Invalid Content-Type",
                                  detail="Content-Type is missing parameter 'dcp-type'," +
                                         " e.g. 'application/json; dcp-type=\"metadata/sample\"'.")

        file = UploadedFile(upload_area=self, name=filename, content_type=str(media_type), data=content)

        checksummer = UploadedFileChecksummer(uploaded_file=file)
        checksum_id = str(uuid.uuid4())
        checksum_event = UploadedFileChecksumEvent(file_id=f"{self.key_prefix}{filename}",
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
        key = f"{self.key_prefix}{filename}"
        return UploadedFile.from_s3_key(self, key)

    def is_extant(self) -> bool:
        record = get_pg_record('upload_area', self.uuid)
        if record and record['status'] != 'DELETED':
            return True
        else:
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

    def _db_record(self):
        return get_pg_record('upload_area', self.uuid)

    def _create_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        create_pg_record("upload_area", prop_vals_dict)

    def _update_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        update_pg_record("upload_area", prop_vals_dict)
