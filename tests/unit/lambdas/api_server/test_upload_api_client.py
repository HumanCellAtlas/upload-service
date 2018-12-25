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
from upload.common.database import UploadDB

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa


class TestUploadApiClient(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        # Environment
        self.api_key = "unguessable"
        self.environment = {
            'INGEST_API_KEY': self.api_key,
            'INGEST_AMQP_SERVER': 'foo',
            'CSUM_DOCKER_IMAGE': 'bogoimage'
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()
        # Setup authentication
        self.authentication_header = {'Api-Key': self.api_key}
        # Setup app
        self.client = client_for_test_api_server()

    def tearDown(self):
        super().tearDown()
        self.environmentor.exit()

    def _create_area(self):
        area_uuid = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_uuid}", headers=self.authentication_header)
        return area_uuid

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_update_event_with_validation_event(self, mock_format_and_send_notification, mock_connect):
        validation_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self.mock_upload_file(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        validation_event = UploadedFileValidationEvent(file_id=s3obj.key,
                                                       validation_id=validation_id,
                                                       job_id='12345',
                                                       status="SCHEDULED")
        validation_event.create_record()
        validation_event.status = "VALIDATING"
        response = update_event(validation_event, uploaded_file.info(), self.client)
        self.assertEqual(response.status_code, 204)
        record = UploadDB().get_pg_record("validation", validation_id)
        self.assertEqual(record["status"], "VALIDATING")
        self.assertEqual(str(type(record.get("validation_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(record["validation_ended_at"], None)
        self.assertEqual(record.get("results"), None)

        validation_event.status = "VALIDATED"
        response = update_event(validation_event, uploaded_file.info(), self.client)
        self.assertEqual(response.status_code, 204)
        record = UploadDB().get_pg_record("validation", validation_id)
        self.assertEqual(record["status"], "VALIDATED")
        self.assertEqual(str(type(record.get("validation_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(str(type(record.get("validation_ended_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(record.get("results"), uploaded_file.info())

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_update_event_with_checksum_event(self, mock_format_and_send_notification, mock_connect):
        checksum_id = str(uuid.uuid4())
        area_uuid = self._create_area()
        s3obj = self.mock_upload_file(area_uuid, 'foo.json')
        upload_area = UploadArea(area_uuid)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        checksum_event = UploadedFileChecksumEvent(file_id=s3obj.key,
                                                   checksum_id=checksum_id,
                                                   job_id='12345',
                                                   status="SCHEDULED")
        checksum_event.create_record()

        checksum_event.status = "CHECKSUMMING"
        response = update_event(checksum_event, uploaded_file.info(), self.client)
        self.assertEqual(response.status_code, 204)
        record = UploadDB().get_pg_record("checksum", checksum_id)
        self.assertEqual(record["status"], "CHECKSUMMING")
        self.assertEqual(str(type(record.get("checksum_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(record["checksum_ended_at"], None)

        checksum_event.status = "CHECKSUMMED"
        response = update_event(checksum_event, uploaded_file.info(), self.client)
        self.assertEqual(response.status_code, 204)
        record = UploadDB().get_pg_record("checksum", checksum_id)
        self.assertEqual(record["status"], "CHECKSUMMED")
        self.assertEqual(str(type(record.get("checksum_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(str(type(record.get("checksum_ended_at"))), "<class 'datetime.datetime'>")
