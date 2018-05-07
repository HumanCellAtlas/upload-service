#!/usr/bin/env python3.6

import os, sys
import uuid
from unittest.mock import patch

import boto3

from ... import UploadTestCaseUsingMockAWS, EnvironmentSetup
from . import client_for_test_api_server

from upload.common.upload_api_client import update_event
from upload.common.uploaded_file import UploadedFile
from upload.common.upload_area import UploadArea
from upload.common.validation_event import UploadedFileValidationEvent
from upload.common.checksum_event import UploadedFileChecksumEvent
from upload.common.database import get_pg_record

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa


class TestDatabase(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        # Setup upload bucket
        self.deployment_stage = 'test'
        self.upload_bucket_name = f'bogobucket'
        self.upload_bucket = boto3.resource('s3').Bucket(self.upload_bucket_name)
        self.upload_bucket.create()
        # Setup authentication
        self.api_key = "foo"
        os.environ['INGEST_API_KEY'] = self.api_key
        self.authentication_header = {'Api-Key': self.api_key}
        # Setup app
        self.environment = {
            'BUCKET_NAME': self.upload_bucket_name,
            'DEPLOYMENT_STAGE': self.deployment_stage,
            'INGEST_AMQP_SERVER': 'foo',
            'CSUM_JOB_Q_ARN': 'bogoqarn',
            'CSUM_JOB_ROLE_ARN': 'bogorolearn',
            'CSUM_DOCKER_IMAGE': 'bogoimage'
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()

        self.client = client_for_test_api_server()

    def tearDown(self):
        super().tearDown()
        self.environmentor.exit()

    @patch('upload.common.upload_area.UploadArea.IAM_SETTLE_TIME_SEC', 0)
    def _create_area(self):
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)
        return area_id

    def _mock_upload_file(self, area_id, filename, contents="foo", content_type="application/json",
                          checksums=None):
        checksums = {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'} if not checksums else checksums
        file1_key = f"{area_id}/{filename}"
        s3obj = self.upload_bucket.Object(file1_key)
        s3obj.put(Body=contents, ContentType=content_type)
        boto3.client('s3').put_object_tagging(Bucket=self.upload_bucket_name, Key=file1_key, Tagging={
            'TagSet': [
                {'Key': 'hca-dss-content-type', 'Value': content_type},
                {'Key': 'hca-dss-s3_etag', 'Value': checksums['s3_etag']},
                {'Key': 'hca-dss-sha1', 'Value': checksums['sha1']},
                {'Key': 'hca-dss-sha256', 'Value': checksums['sha256']},
                {'Key': 'hca-dss-crc32c', 'Value': checksums['crc32c']}
            ]
        })
        return s3obj

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_update_event_with_validation_event(self, mock_format_and_send_notification, mock_connect):
        validation_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self._mock_upload_file(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3obj)
        uploaded_file.create_record()
        validation_event = UploadedFileValidationEvent(file_id=s3obj.key,
                                                       validation_id=validation_id,
                                                       job_id='12345',
                                                       status="SCHEDULED")
        validation_event.create_record()
        validation_event.status = "VALIDATING"
        response = update_event(validation_event, uploaded_file.info(), self.client)
        self.assertEqual(response.status_code, 204)
        record = get_pg_record("validation", validation_id)
        self.assertEqual(record["status"], "VALIDATING")
        self.assertEqual(str(type(record.get("validation_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(record["validation_ended_at"], None)
        self.assertEqual(record.get("results"), None)

        validation_event.status = "VALIDATED"
        response = update_event(validation_event, uploaded_file.info(), self.client)
        self.assertEqual(response.status_code, 204)
        record = get_pg_record("validation", validation_id)
        self.assertEqual(record["status"], "VALIDATED")
        self.assertEqual(str(type(record.get("validation_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(str(type(record.get("validation_ended_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(record.get("results"), uploaded_file.info())

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_update_event_with_checksum_event(self, mock_format_and_send_notification, mock_connect):
        checksum_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self._mock_upload_file(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3obj)
        uploaded_file.create_record()
        checksum_event = UploadedFileChecksumEvent(file_id=s3obj.key,
                                                   checksum_id=checksum_id,
                                                   job_id='12345',
                                                   status="SCHEDULED")
        checksum_event.create_record()

        checksum_event.status = "CHECKSUMMING"
        response = update_event(checksum_event, uploaded_file.info(), self.client)
        self.assertEqual(response.status_code, 204)
        record = get_pg_record("checksum", checksum_id)
        self.assertEqual(record["status"], "CHECKSUMMING")
        self.assertEqual(str(type(record.get("checksum_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(record["checksum_ended_at"], None)

        checksum_event.status = "CHECKSUMMED"
        response = update_event(checksum_event, uploaded_file.info(), self.client)
        self.assertEqual(response.status_code, 204)
        record = get_pg_record("checksum", checksum_id)
        self.assertEqual(record["status"], "CHECKSUMMED")
        self.assertEqual(str(type(record.get("checksum_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(str(type(record.get("checksum_ended_at"))), "<class 'datetime.datetime'>")
