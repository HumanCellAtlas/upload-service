import json
import os
import uuid
import time

import boto3
from tenacity import retry, wait_fixed, stop_after_attempt

from dcplib.media_types import DcpMediaType

from .dss_checksums import DssChecksums
from .uploaded_file import UploadedFile
from .checksum_event import ChecksumEvent
from .exceptions import UploadException
from .upload_config import UploadConfig
from .logging import get_logger

if not os.environ.get("CONTAINER"):
    from .database import UploadDB

logger = get_logger(__name__)

s3 = boto3.resource('s3')
sqs = boto3.resource('sqs')
lambda_client = boto3.client('lambda')


class UploadArea:

    def __init__(self, uuid):
        self.config = self._get_and_check_config()
        self.db_id = None
        self.uuid = uuid
        self.status = None
        self.key_prefix = f"{self.uuid}/"
        self.key_prefix_length = len(self.key_prefix)
        self._bucket = s3.Bucket(self.bucket_name)
        self.db = UploadDB()
        self._db_load()

    def __str__(self):
        return f"UploadArea(id={self.db_id}, uuid={self.uuid}, status={self.status})"

    @property
    def bucket_name(self):
        return self.config.bucket_name

    @property
    def staging_bucket_arn(self):
        # The wranglers have been using staging for initial submissions.
        # We need to give the upload submitter role access to this bucket to allow for cross bucket transfer
        return self.config.staging_bucket_arn

    @property
    def _deployment_stage(self):
        return os.environ['DEPLOYMENT_STAGE']

    @property
    def uri(self):
        return f"s3://{self._bucket.name}/{self.key_prefix}"

    def update_or_create(self):
        self._db_load()
        if self.db_id:
            self._db_update()
        else:
            self.status = "UNLOCKED"
            self.db_id = self._db_create()

    def is_extant(self) -> bool:
        self._db_load()
        if self.db_id and self.status != 'DELETED':
            return True
        else:
            return False

    def credentials(self):
        self._db_load()
        if not self.status == 'UNLOCKED':
            raise UploadException(status=409, title="Upload Area is Not Writable",
                                  detail=f"Cannot issue credentials, upload area {self.uuid} is {self.status}")

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
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:Get*",
                        "s3:List*"
                    ],
                    "Resource": [
                        f"{self.staging_bucket_arn}/*",
                        f"{self.staging_bucket_arn}",
                        "arn:aws:s3:::org-humancellatlas-dcp-test-data",
                        "arn:aws:s3:::org-humancellatlas-dcp-test-data/*"
                    ]
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
        # This is currently invoked by scheduled deletions in sqs
        self.status = "DELETING"
        self._db_update()
        area_status = self._empty_upload_area()
        self.status = area_status
        self._db_update()

    def ls(self):
        return {'files': self._file_list()}

    def lock(self):
        self.status = "LOCKED"
        self._db_update()

    def unlock(self):
        self.status = "UNLOCKED"
        self._db_update()

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
        response = sqs.meta.client.send_message(QueueUrl=self.config.csum_upload_q_url,
                                                MessageBody=json.dumps(payload))
        status = response['ResponseMetadata']['HTTPStatusCode']
        if status != 200:
            raise UploadException(status=500, title="Internal error",
                                  detail=f"Adding file upload message for {self.key_prefix}{filename} "
                                         f"was unsuccessful to SQS {self.config.csum_upload_q_url} )")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
    def add_upload_area_to_delete_sqs(self):
        self.status = "DELETION_QUEUED"
        self._db_update()
        payload = {
            'area_uuid': f"{self.uuid}"
        }
        response = sqs.meta.client.send_message(QueueUrl=self.config.area_deletion_q_url,
                                                MessageBody=json.dumps(payload))
        status = response['ResponseMetadata']['HTTPStatusCode']
        if status != 200:
            raise UploadException(status=500, title="Internal error",
                                  detail=f"Adding delete message for area {self.uuid} \
                                        was unsuccessful to sqs {self.config.area_deletion_q_url} )")
        logger.info(f"added deletion of area {self.uuid} to sqs")

    def store_file(self, filename, content, content_type):
        media_type = DcpMediaType.from_string(content_type)
        if 'dcp-type' not in media_type.parameters:
            raise UploadException(status=400, title="Invalid Content-Type",
                                  detail="Content-Type is missing parameter 'dcp-type',"
                                         " e.g. 'application/json; dcp-type=\"metadata/sample\"'.")

        file = UploadedFile.create(upload_area=self, name=filename, content_type=str(media_type), data=content)
        checksum_id = str(uuid.uuid4())
        checksum_event = ChecksumEvent(file_id=file.db_id,
                                       checksum_id=checksum_id,
                                       status="CHECKSUMMING")
        checksum_event.create_record()

        checksums = DssChecksums(s3_object=file.s3object)
        checksums.compute(report_progress=True)
        checksums.save_as_tags_on_s3_object()
        file.checksums = dict(checksums)

        checksum_event.status = "CHECKSUMMED"
        checksum_event.update_record()
        return file

    def uploaded_file(self, filename):
        key = f"{self.key_prefix}{filename}"
        return UploadedFile.from_s3_key(self, key)

    def retrieve_file_checksum_statuses_for_upload_area(self):
        checksum_status = {
            'TOTAL_NUM_FILES': self.retrieve_file_count_for_upload_area(),
            'CHECKSUMMING': 0,
            'CHECKSUMMED': 0,
            'CHECKSUMMING_UNSCHEDULED': 0
        }
        query_result = self.db.run_query_with_params(
            "SELECT status, COUNT(DISTINCT checksum.file_id) "
            "FROM checksum "
            "INNER JOIN file ON checksum.file_id = file.id "
            "WHERE file.upload_area_id = %s GROUP BY status;", (self.db_id,))
        results = query_result.fetchall()
        checksumming_file_count = 0
        if len(results) > 0:
            for status in results:
                checksum_status[status[0]] = status[1]
                checksumming_file_count += status[1]
        checksum_status['CHECKSUMMING_UNSCHEDULED'] = checksum_status['TOTAL_NUM_FILES'] - checksumming_file_count
        return checksum_status

    def retrieve_file_validation_statuses_for_upload_area(self):
        query_result = self.db.run_query_with_params(
            "SELECT status, COUNT(validation.id) "
            "FROM validation "
            "INNER JOIN validation_files ON validation.id = validation_files.validation_id  "
            "INNER JOIN file ON validation_files.file_id = file.id "
            "WHERE file.upload_area_id = %s GROUP BY status;", (self.db_id,))
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
                                                     self.db_id)
        results = query_result.fetchall()
        return results[0][0]

    def _get_and_check_config(self):
        config = UploadConfig()
        assert config.bucket_name is not None, "bucket_name is not in config"
        assert config.csum_upload_q_url is not None, "csum_upload_q_url is not in config"
        assert config.area_deletion_q_url is not None, "area_deletion_q_url is not in config"
        assert config.area_deletion_lambda_name is not None, "area_deletion_lambda_name is not in config"
        assert config.upload_submitter_role_arn is not None, "upload_submitter_role_arn is not in config"
        return config

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
        logger.info(f"starting deletion of area {self.uuid}")
        lambda_timeout = self._retrieve_upload_area_deletion_lambda_timeout() - 30
        deletion_start_time = time.time()
        paginator = s3.meta.client.get_paginator('list_objects')
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.uuid):
            if 'Contents' in page:
                for o in page['Contents']:
                    elapsed_time = time.time() - deletion_start_time
                    if elapsed_time > lambda_timeout:
                        # Lambda will timeout in less than 1 minute. Re-add this area to deletion sqs.
                        self.add_upload_area_to_delete_sqs()
                        return "DELETION_QUEUED"
                    s3.meta.client.delete_object(Bucket=self.bucket_name, Key=o['Key'])
        logger.info(f"completed deletion of area {self.uuid}")
        return "DELETED"

    def _retrieve_upload_area_deletion_lambda_timeout(self):
        response = lambda_client.get_function(FunctionName=self.config.area_deletion_lambda_name)
        return response['Configuration']['Timeout']

    def _db_load(self):
        data = self.db.get_pg_record('upload_area', self.uuid, column='uuid')
        if data:
            self.db_id = data['id']
            self.status = data['status']

    def _db_serialize(self):
        data = {
            "uuid": self.uuid,
            "bucket_name": self.bucket_name,
            "status": self.status
        }
        if self.db_id is not None:
            data["id"] = self.db_id
        return data

    def _db_create(self):
        prop_vals_dict = self._db_serialize()
        new_row_id = self.db.create_pg_record("upload_area", prop_vals_dict)
        return new_row_id

    def _db_update(self):
        prop_vals_dict = self._db_serialize()
        self.db.update_pg_record("upload_area", prop_vals_dict)
