import uuid
from unittest.mock import patch

from upload.common.upload_area import UploadArea
from upload.common.uploaded_file import UploadedFile
from upload.lambdas.api_server.validation_scheduler import ValidationScheduler, MAX_FILE_SIZE_IN_BYTES

from ... import UploadTestCaseUsingMockAWS


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
        uploaded_file = UploadedFile(upload_area=self.upload_area,
                                     name="file2",
                                     content_type="application/octet-stream; dcp-type=data",
                                     data="file2_content")
        scheduler = ValidationScheduler(uploaded_file)

        file_validatable = scheduler.check_file_can_be_validated()

        self.assertEqual(False, file_validatable)

    def test_file_validation_event_can_be_created_with_hash(self):
        uploaded_file = UploadedFile(upload_area=self.upload_area,
                                     name="file2#",
                                     content_type="application/octet-stream; dcp-type=data",
                                     data="file2_content")
        scheduler = ValidationScheduler(uploaded_file)
        scheduler.batch_job_id = "123456"
        validation_id = str(uuid.uuid4())

        validation_event = scheduler._create_scheduled_validation_event("test_docker_image", validation_id, None)

        self.assertEqual(validation_event.job_id, "123456")
        self.assertEqual(validation_event.docker_image, "test_docker_image")

    @patch('upload.common.upload_area.UploadedFile.size', MAX_FILE_SIZE_IN_BYTES - 1)
    def test_check_file_can_be_validated_returns_true_if_file_is_not_too_large(self):
        uploaded_file = UploadedFile(upload_area=self.upload_area,
                                     name="file2",
                                     content_type="application/octet-stream; dcp-type=data",
                                     data="file2_content")
        scheduler = ValidationScheduler(uploaded_file)

        file_validatable = scheduler.check_file_can_be_validated()

        self.assertEqual(True, file_validatable)
