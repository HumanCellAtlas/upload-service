import uuid
import json
from unittest.mock import patch

from upload.common.upload_area import UploadArea
from upload.common.uploaded_file import UploadedFile
from upload.common.validation_scheduler import ValidationScheduler, MAX_FILE_SIZE_IN_BYTES
from upload.common.database import UploadDB

from .. import UploadTestCaseUsingMockAWS


class TestValidationScheduler(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()

        self.upload_area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.upload_area_id)
        self.upload_area.update_or_create()

    def tearDown(self):
        super().tearDown()
        pass

    @patch('upload.common.upload_area.UploadedFile.size', MAX_FILE_SIZE_IN_BYTES + 1)
    def test_check_file_can_be_validated_returns_false_if_file_is_too_large_for_validation(self):
        uploaded_file = UploadedFile.create(upload_area=self.upload_area,
                                            name="file2",
                                            content_type="application/octet-stream; dcp-type=data",
                                            data="file2_content")
        scheduler = ValidationScheduler(uploaded_file)

        file_validatable = scheduler.check_file_can_be_validated()

        self.assertEqual(False, file_validatable)

    def test_file_validation_event_can_be_created_with_hash(self):
        uploaded_file = UploadedFile.create(upload_area=self.upload_area,
                                            name="file2#",
                                            content_type="application/octet-stream; dcp-type=data",
                                            data="file2_content")
        scheduler = ValidationScheduler(uploaded_file)
        validation_id = str(uuid.uuid4())

        validation_event = scheduler._create_validation_event("test_docker_image", validation_id, None)

        self.assertEqual(validation_event.docker_image, "test_docker_image")
        self.assertEqual(validation_event.status, "SCHEDULING_QUEUED")

    def test_update_validation_event(self):
        uploaded_file = UploadedFile.create(upload_area=self.upload_area,
                                            name="file2#",
                                            content_type="application/octet-stream; dcp-type=data",
                                            data="file2_content")
        scheduler = ValidationScheduler(uploaded_file)
        scheduler.batch_job_id = "123456"
        validation_id = str(uuid.uuid4())
        validation_event = scheduler._create_validation_event("test_docker_image", validation_id, None)

        self.assertEqual(validation_event.job_id, None)
        validation_event = scheduler._update_validation_event("test_docker_image", validation_id, None)

        self.assertEqual(validation_event.job_id, "123456")
        self.assertEqual(validation_event.status, "SCHEDULED")

    @patch('upload.common.upload_area.UploadedFile.size', MAX_FILE_SIZE_IN_BYTES - 1)
    def test_check_file_can_be_validated_returns_true_if_file_is_not_too_large(self):
        uploaded_file = UploadedFile.create(upload_area=self.upload_area,
                                            name="file2",
                                            content_type="application/octet-stream; dcp-type=data",
                                            data="file2_content")
        scheduler = ValidationScheduler(uploaded_file)

        file_validatable = scheduler.check_file_can_be_validated()

        self.assertEqual(True, file_validatable)

    def test_add_to_pre_batch_validation_sqs(self):
        uploaded_file = UploadedFile.create(upload_area=self.upload_area,
                                            name="file2",
                                            content_type="application/octet-stream; dcp-type=data",
                                            data="file2_content")
        validation_scheduler = ValidationScheduler(uploaded_file)

        validation_uuid = validation_scheduler.add_to_pre_batch_validation_sqs("filename123",
                                                                               "test_docker_image",
                                                                               {"variable": "variable"},
                                                                               "123456")

        message = self.sqs.meta.client.receive_message(QueueUrl='test_pre_batch_validation_q_url')
        message_body = json.loads(message['Messages'][0]['Body'])
        record = UploadDB().get_pg_record("validation", validation_uuid, column='id')
        self.assertEqual(message_body["filename"], "filename123")
        self.assertEqual(message_body["validation_id"], validation_uuid)
        self.assertEqual(message_body["validator_docker_image"], "test_docker_image")
        self.assertEqual(message_body["environment"], {"variable": "variable"})
        self.assertEqual(message_body["orig_validation_id"], "123456")
        self.assertEqual(message_body["upload_area_uuid"], uploaded_file.upload_area.uuid)
        self.assertEqual(record["status"], "SCHEDULING_QUEUED")
