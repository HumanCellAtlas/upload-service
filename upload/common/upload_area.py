import json
import os
import uuid

import boto3
from tenacity import retry, wait_fixed, stop_after_attempt

from dcplib.media_types import DcpMediaType

from .checksum import UploadedFileChecksummer
from .uploaded_file import UploadedFile
from .checksum_event import UploadedFileChecksumEvent
from .exceptions import UploadException
from .upload_config import UploadConfig
from .logging import get_logger

if not os.environ.get("CONTAINER"):
    from .database import UploadDB

logger = get_logger(__name__)

s3 = boto3.resource('s3')
sqs = boto3.resource('sqs')


class UploadArea:

    def __init__(self, uuid):
        self.uuid = uuid
        self.status = None
        self.config = UploadConfig()
        self.key_prefix = f"{self.uuid}/"
        self.key_prefix_length = len(self.key_prefix)
        self._bucket = s3.Bucket(self.bucket_name)
        self.csum_sqs_url = self.config.csum_job_q_url
        self.db = UploadDB()

    @property
    def bucket_name(self):
        return self.config.bucket_name

    @property
    def _deployment_stage(self):
        return os.environ['DEPLOYMENT_STAGE']

    @property
    def uri(self):
        return f"s3://{self._bucket.name}/{self.key_prefix}"

    def update_or_create(self):
        self.status = "UNLOCKED"
        if self._db_record():
            self._update_record()
        else:
            self._create_record()

    def credentials(self):
        record = self._db_record()
        if not record['status'] == 'UNLOCKED':
            raise UploadException(status=409, title="Upload Area is Not Writable",
                                  detail=f"Cannot issue credentials, upload area {self.uuid} is {record['status']}")

        sts = boto3.client("sts")
        # Note that this policy builds on top of the one stored at self.config.upload_submitter_role_arn.
        # That policy provides access to the entire bucket, and this one narrows it to one upload area.
        # The assume_role call below merges them.
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
            DurationSeconds=3600,
            ExternalId="TBD",
            Policy=policy_json
        )
        creds = response['Credentials']
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

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
    def add_uploaded_file_to_csum_daemon_sqs(self, filename):
        payload = {
            'Records': [{
                'eventName': 'ObjectCreated:Put',
                "s3": {
                    "bucket": {
                        "name": f"{self.bucket_name}"
                    },
                    "object": {
                        "key": f"{self.key_prefix}{filename}"
                    }
                }
            }]
        }
        response = sqs.meta.client.send_message(QueueUrl=self.csum_sqs_url, MessageBody=json.dumps(payload))
        status = response['ResponseMetadata']['HTTPStatusCode']
        if status != 200:
            raise UploadException(f"Adding file upload message for {self.key_prefix}{filename} \
                                    was unsuccessful to sqs {self.csum_job_q_url} )")

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
        record = self.db.get_pg_record('upload_area', self.uuid)
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
        return self.db.get_pg_record('upload_area', self.uuid)

    def _create_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        self.db.create_pg_record("upload_area", prop_vals_dict)

    def _update_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        self.db.update_pg_record("upload_area", prop_vals_dict)

    def retrieve_file_checksum_statuses_for_upload_area(self):
        checksum_status = {
            'TOTAL_NUM_FILES': self.retrieve_file_count_for_upload_area(),
            'CHECKSUMMING': 0,
            'CHECKSUMMED': 0,
            'CHECKSUMMING_UNSCHEDULED': 0
        }
        query_result = self.db.run_query_with_params("SELECT status, COUNT(DISTINCT checksum.file_id) FROM checksum "
                                                     "WHERE file_id LIKE %s GROUP BY  status;", (f"{self.uuid}/%",))
        results = query_result.fetchall()
        checksumming_file_count = 0
        if len(results) > 0:
            for status in results:
                checksum_status[status[0]] = status[1]
                checksumming_file_count += status[1]
        checksum_status['CHECKSUMMING_UNSCHEDULED'] = checksum_status['TOTAL_NUM_FILES'] - checksumming_file_count
        return checksum_status

    def retrieve_file_validation_statuses_for_upload_area(self):
        query_result = self.db.run_query_with_params("SELECT status, COUNT(DISTINCT validation.file_id) FROM validation"
                                                     " WHERE file_id LIKE %s GROUP BY  status;", (f"{self.uuid}/%",))
        results = query_result.fetchall()
        validation_status_dict = {
            'VALIDATING': 0,
            'VALIDATED': 0,
            'SCHEDULED': 0
        }
        if len(results) > 0:
            for status in results:
                validation_status_dict[status[0]] = status[1]
        return validation_status_dict

    def retrieve_file_count_for_upload_area(self):
        query_result = self.db.run_query_with_params("SELECT COUNT(DISTINCT name) FROM file WHERE upload_area_id=%s",
                                                     self.uuid)
        results = query_result.fetchall()
        return results[0][0]
