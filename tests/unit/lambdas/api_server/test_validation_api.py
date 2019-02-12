import json
import uuid
from unittest.mock import patch
import urllib.parse

from upload.common.upload_area import UploadArea
from upload.common.uploaded_file import UploadedFile
from upload.common.validation_event import ValidationEvent
from upload.common.validation_scheduler import MAX_FILE_SIZE_IN_BYTES
from upload.common.database import UploadDB

from . import client_for_test_api_server
from ... import UploadTestCaseUsingMockAWS, EnvironmentSetup


class TestValidationApi(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        # Environment
        self.api_key = "foo"
        self.environment = {
            'INGEST_API_KEY': self.api_key,
            'INGEST_AMQP_SERVER': 'foo',
            'CSUM_DOCKER_IMAGE': 'bogo_image',
            'API_HOST': 'bogohost'
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
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)
        return area_id

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_validation_statuses_for_upload_area(self, mock_format_and_send_notification):
        area_id = self._create_area()
        upload_area = UploadArea(area_id)

        validation1_id = str(uuid.uuid4())
        validation2_id = str(uuid.uuid4())
        validation3_id = str(uuid.uuid4())
        validation4_id = str(uuid.uuid4())

        s3obj1 = self.mock_upload_file_to_s3(area_id, 'foo1.json')
        s3obj2 = self.mock_upload_file_to_s3(area_id, 'foo2.json')
        s3obj3 = self.mock_upload_file_to_s3(area_id, 'foo3.json')
        s3obj4 = self.mock_upload_file_to_s3(area_id, 'foo4.json')

        f1 = UploadedFile(upload_area, s3object=s3obj1)
        f2 = UploadedFile(upload_area, s3object=s3obj2)
        f3 = UploadedFile(upload_area, s3object=s3obj3)
        f4 = UploadedFile(upload_area, s3object=s3obj4)

        validation_event1 = ValidationEvent(file_id=f1.db_id,
                                            validation_id=validation1_id,
                                            job_id='12345',
                                            status="SCHEDULED")
        validation_event2 = ValidationEvent(file_id=f2.db_id,
                                            validation_id=validation2_id,
                                            job_id='23456',
                                            status="VALIDATING")
        validation_event3 = ValidationEvent(file_id=f3.db_id,
                                            validation_id=validation3_id,
                                            job_id='34567',
                                            status="VALIDATED")
        validation_event4 = ValidationEvent(file_id=f4.db_id,
                                            validation_id=validation4_id,
                                            job_id='45678',
                                            status="VALIDATING")
        validation_event3.results = 'VALID'
        validation_event1.create_record()
        validation_event2.create_record()
        validation_event3.create_record()
        validation_event4.create_record()

        response = self.client.get(f"/v1/area/{area_id}/validations")
        expected_data = {'SCHEDULED': 1, 'VALIDATED': 1, 'VALIDATING': 2}
        self.assertEqual(expected_data, response.get_json())

    @patch('upload.common.uploaded_file.UploadedFile.size', MAX_FILE_SIZE_IN_BYTES + 1)
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_schedule_file_validation_raises_error_if_file_too_large(self, mock_format_and_send_notification):
        area_id = self._create_area()
        self.mock_upload_file_to_s3(area_id, 'foo.json')
        response = self.client.put(
            f"/v1/area/{area_id}/foo.json/validate",
            headers=self.authentication_header,
            json={"validator_image": "humancellatlas/upload-validator-example"}
        )
        expected_decoded_response_data = '{\n  "status": 400,\n  "title": "File too large for validation"\n}\n'
        self.assertEqual(expected_decoded_response_data, response.data.decode())

        self.assertEqual(400, response.status_code)

    @patch('upload.common.upload_area.UploadedFile.size', MAX_FILE_SIZE_IN_BYTES - 1)
    @patch('upload.lambdas.api_server.v1.area.ValidationScheduler.add_to_validation_sqs')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_schedule_file_validation_doesnt_raise_error_for_correct_file_size(self, mock_format_and_send_notification,
                                                                               mock_validate):
        mock_validate.return_value = 4472093160
        area_id = self._create_area()
        self.mock_upload_file_to_s3(area_id, 'foo.json')
        response = self.client.put(
            f"/v1/area/{area_id}/foo.json/validate",
            headers=self.authentication_header,
            json={"validator_image": "humancellatlas/upload-validator-example"}
        )
        self.assertEqual(200, response.status_code)

    @patch('upload.common.upload_area.UploadedFile.size', MAX_FILE_SIZE_IN_BYTES - 1)
    @patch('upload.lambdas.api_server.v1.area.ValidationScheduler.add_to_validation_sqs')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_schedule_file_validation_works_for_hash_percent_encoding(self, mock_format_and_send_notification,
                                                                      mock_validate):
        mock_validate.return_value = 4472093160
        area_id = self._create_area()
        filename = 'green#.json'
        self.mock_upload_file_to_s3(area_id, filename)
        url_safe_filename = urllib.parse.quote(filename)
        response = self.client.put(
            f"/v1/area/{area_id}/{url_safe_filename}/validate",
            headers=self.authentication_header,
            json={"validator_image": "humancellatlas/upload-validator-example"}
        )
        self.assertEqual(200, response.status_code)

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_unscheduled_status_file_validation(self, mock_format_and_send_notification):
        area_id = self._create_area()
        s3obj = self.mock_upload_file_to_s3(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        UploadedFile(upload_area, s3object=s3obj)
        response = self.client.get(f"/v1/area/{area_id}/foo.json/validate")
        validation_status = response.get_json()['validation_status']
        self.assertEqual(validation_status, "UNSCHEDULED")

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_scheduled_status_file_validation(self, mock_format_and_send_notification):
        validation_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self.mock_upload_file_to_s3(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        validation_event = ValidationEvent(file_id=uploaded_file.db_id,
                                           validation_id=validation_id,
                                           job_id='12345',
                                           status="SCHEDULED")
        validation_event.create_record()
        response = self.client.get(f"/v1/area/{area_id}/foo.json/validate")
        validation_status = response.get_json()['validation_status']
        self.assertEqual(validation_status, "SCHEDULED")

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_validating_status_file_validation(self, mock_format_and_send_notification):
        validation_id = str(uuid.uuid4())
        orig_val_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self.mock_upload_file_to_s3(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        validation_event = ValidationEvent(file_id=uploaded_file.db_id,
                                           validation_id=validation_id,
                                           job_id='12345',
                                           status="SCHEDULED",
                                           docker_image="test_docker_image",
                                           original_validation_id=orig_val_id)
        validation_event.create_record()
        data = {
            "status": "VALIDATING",
            "job_id": validation_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_id}/update_validation/{validation_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(204, response.status_code)
        record = UploadDB().get_pg_record("validation", validation_id)
        self.assertEqual("test_docker_image", record["docker_image"])
        self.assertEqual(validation_id, record["id"])
        self.assertEqual(orig_val_id, record["original_validation_id"])
        self.assertEqual("VALIDATING", record["status"])
        self.assertEqual("<class 'datetime.datetime'>", str(type(record.get("validation_started_at"))))
        self.assertEqual(None, record["validation_ended_at"])
        self.assertEqual(None, record.get("results"))
        response = self.client.get(f"/v1/area/{area_id}/foo.json/validate")
        validation_status = response.get_json()['validation_status']
        self.assertEqual(validation_status, "VALIDATING")
        mock_format_and_send_notification.assert_not_called()

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_validated_status_file_validation(self, mock_format_and_send_notification):
        validation_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self.mock_upload_file_to_s3(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        validation_event = ValidationEvent(file_id=uploaded_file.db_id,
                                           validation_id=validation_id,
                                           job_id='12345',
                                           status="SCHEDULED",
                                           docker_image="test_docker_image")
        validation_event.create_record()
        data = {
            "status": "VALIDATING",
            "job_id": validation_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_id}/update_validation/{validation_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        data = {
            "status": "VALIDATED",
            "job_id": validation_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_id}/update_validation/{validation_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(204, response.status_code)
        mock_format_and_send_notification.assert_called_once_with({
            'upload_area_id': area_id,
            'name': 'foo.json',
            'size': 3,
            'last_modified': s3obj.last_modified.isoformat(),
            'content_type': "application/json",
            'url': f"s3://{self.upload_config.bucket_name}/{area_id}/foo.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        record = UploadDB().get_pg_record("validation", validation_id)
        self.assertEqual("VALIDATED", record["status"])
        self.assertEqual("test_docker_image", record["docker_image"])
        self.assertEqual("<class 'datetime.datetime'>", str(type(record.get("validation_started_at"))))
        self.assertEqual("<class 'datetime.datetime'>", str(type(record.get("validation_ended_at"))))
        self.assertEqual(uploaded_file.info(), record.get("results"))
        response = self.client.get(f"/v1/area/{area_id}/foo.json/validate")
        validation_status = response.get_json()['validation_status']
        self.assertEqual(validation_status, "VALIDATED")
