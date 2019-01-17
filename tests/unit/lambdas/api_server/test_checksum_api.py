import json
import uuid
from unittest.mock import patch

import boto3

from upload.common.upload_area import UploadArea
from upload.common.uploaded_file import UploadedFile
from upload.common.checksum_event import ChecksumEvent

from . import client_for_test_api_server
from ... import UploadTestCaseUsingMockAWS, EnvironmentSetup


class TestChecksumApi(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        # Environment
        self.api_key = "foo"
        self.environment = {
            'INGEST_API_KEY': self.api_key,
            'INGEST_AMQP_SERVER': 'foo',
            'CSUM_DOCKER_IMAGE': 'bogo_image',
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()

        # Authentication
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

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_unscheduled_status_file_checksum(self, mock_format_and_send_notification):
        area_uuid = self._create_area()
        s3obj = self.mock_upload_file_to_s3(area_uuid, 'foo.json')
        upload_area = UploadArea(area_uuid)
        UploadedFile(upload_area, s3object=s3obj)
        response = self.client.get(f"/v1/area/{area_uuid}/foo.json/checksum")
        checksum_status = response.get_json()['checksum_status']
        self.assertEqual(checksum_status, "UNSCHEDULED")

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_scheduled_status_file_checksum(self, mock_format_and_send_notification):
        checksum_id = str(uuid.uuid4())
        area_uuid = self._create_area()
        s3obj = self.mock_upload_file_to_s3(area_uuid, 'foo.json')
        upload_area = UploadArea(area_uuid)
        UploadedFile(upload_area, s3object=s3obj)
        checksum_event = ChecksumEvent(file_id=s3obj.key,
                                       checksum_id=checksum_id,
                                       job_id='12345',
                                       status="SCHEDULED")
        checksum_event.create_record()
        response = self.client.get(f"/v1/area/{area_uuid}/foo.json/checksum")
        checksum_status = response.get_json()['checksum_status']
        self.assertEqual(checksum_status, "SCHEDULED")

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_checksumming_status_file_checksum(self, mock_format_and_send_notification):
        checksum_id = str(uuid.uuid4())
        area_uuid = self._create_area()
        s3obj = self.mock_upload_file_to_s3(area_uuid, 'foo.json')
        upload_area = UploadArea(area_uuid)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        checksum_event = ChecksumEvent(file_id=s3obj.key,
                                       checksum_id=checksum_id,
                                       job_id='12345',
                                       status="SCHEDULED")
        checksum_event.create_record()

        data = {
            "status": "CHECKSUMMING",
            "job_id": checksum_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_uuid}/update_checksum/{checksum_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(204, response.status_code)
        response = self.client.get(f"/v1/area/{area_uuid}/foo.json/checksum")
        checksum_status = response.get_json()['checksum_status']
        self.assertEqual(checksum_status, "CHECKSUMMING")

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_checksummed_status_file_checksum(self, mock_format_and_send_notification):
        checksum_id = str(uuid.uuid4())
        area_uuid = self._create_area()
        s3obj = self.mock_upload_file_to_s3(area_uuid, 'foo.json')
        upload_area = UploadArea(area_uuid)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        checksum_event = ChecksumEvent(file_id=s3obj.key,
                                       checksum_id=checksum_id,
                                       job_id='12345',
                                       status="SCHEDULED")
        checksum_event.create_record()

        data = {
            "status": "CHECKSUMMED",
            "job_id": checksum_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_uuid}/update_checksum/{checksum_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(204, response.status_code)
        response = self.client.get(f"/v1/area/{area_uuid}/foo.json/checksum")
        checksum_status = response.get_json()['checksum_status']
        self.assertEqual(checksum_status, "CHECKSUMMED")

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_checksum_statuses_for_upload_area(self, mock_format_and_send_notification):
        area_uuid = self._create_area()
        upload_area = UploadArea(area_uuid)

        checksum1_id = str(uuid.uuid4())
        checksum2_id = str(uuid.uuid4())
        checksum3_id = str(uuid.uuid4())

        s3obj1 = self.mock_upload_file_to_s3(area_uuid, 'foo1.json')
        s3obj2 = self.mock_upload_file_to_s3(area_uuid, 'foo2.json')
        s3obj3 = self.mock_upload_file_to_s3(area_uuid, 'foo3.json')
        s3obj4 = self.mock_upload_file_to_s3(area_uuid, 'foo4.json')
        s3obj5 = self.mock_upload_file_to_s3(area_uuid, 'foo5.json')

        UploadedFile(upload_area, s3object=s3obj1)
        UploadedFile(upload_area, s3object=s3obj2)
        UploadedFile(upload_area, s3object=s3obj3)
        UploadedFile(upload_area, s3object=s3obj4)
        UploadedFile(upload_area, s3object=s3obj5)

        checksum1_event = ChecksumEvent(file_id=s3obj1.key,
                                        checksum_id=checksum1_id,
                                        job_id='12345',
                                        status="SCHEDULED")
        checksum2_event = ChecksumEvent(file_id=s3obj2.key,
                                        checksum_id=checksum2_id,
                                        job_id='23456',
                                        status="CHECKSUMMING")
        checksum3_event = ChecksumEvent(file_id=s3obj3.key,
                                        checksum_id=checksum3_id,
                                        job_id='34567',
                                        status="CHECKSUMMED")
        checksum1_event.create_record()
        checksum2_event.create_record()
        checksum3_event.create_record()

        response = self.client.get(f"/v1/area/{area_uuid}/checksums")
        expected_data = {
            'CHECKSUMMED': 1,
            'CHECKSUMMING': 1,
            'CHECKSUMMING_UNSCHEDULED': 2,
            'SCHEDULED': 1,
            'TOTAL_NUM_FILES': 5
        }

        assert response.get_json() == expected_data
