import uuid

from unittest.mock import patch

from .. import UploadTestCaseUsingMockAWS, EnvironmentSetup
from upload.common.ingest_notifier import IngestNotifier
from upload.common.database import UploadDB
from ..lambdas.api_server import client_for_test_api_server


class TestIngestNotifier(UploadTestCaseUsingMockAWS):

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

    def test_init(self):
        ingest_notifier_one = IngestNotifier("file_uploaded")
        ingest_notifier_two = IngestNotifier("file_validated")

        expected_url_for_one = "https://test_ingest_api_host/messaging/fileUploadInfo"
        expected_url_for_two = "https://test_ingest_api_host/messaging/fileValidationResult"

        self.assertEqual(ingest_notifier_one.ingest_notification_url, expected_url_for_one)
        self.assertEqual(ingest_notifier_two.ingest_notification_url, expected_url_for_two)

    def test_ingest_api_host(self):
        ingest_notifier = IngestNotifier("file_uploaded")
        ingest_api_host = ingest_notifier.ingest_api_host
        self.assertEqual(ingest_api_host, "test_ingest_api_host")

    def test_auth_audience(self):
        ingest_notifier = IngestNotifier("file_uploaded")
        auth_audience = ingest_notifier.auth_audience
        self.assertEqual(auth_audience, "test_auth_audience")

    def test_service_credentials(self):
        ingest_notifier = IngestNotifier("file_uploaded")

        service_credentials = ingest_notifier.service_credentials

        self.assertEqual(service_credentials["private_key"], "test_private_key")
        self.assertEqual(service_credentials["private_key_id"], "test_private_key_id")
        self.assertEqual(service_credentials["client_email"], "test_client_email")

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier._send_notification')
    def test_format_and_send_notification(self, mock_send_notification):
        ingest_notifier = IngestNotifier("file_uploaded")
        area_uuid = self._create_area()
        headers = {'Content-Type': 'application/json; dcp-type="metadata/sample"'}
        headers.update(self.authentication_header)
        self.client.put(f"/v1/area/{area_uuid}/test_file_name", data="exquisite corpse", headers=headers)

        test_payload = {'name': "test_file_name", 'upload_area_id': area_uuid}
        notification_id = ingest_notifier.format_and_send_notification(test_payload)

        record = UploadDB().get_pg_record("notification", notification_id, column="id")
        self.assertEqual(record['status'], "DELIVERED")
        self.assertEqual(record['file_id'], f"{area_uuid}/test_file_name")
        self.assertEqual(record['payload'], test_payload)

    @patch('jwt.encode')
    def test_get_service_jwt(self, mock_encode):
        ingest_notifier = IngestNotifier("file_uploaded")
        mock_encode.return_value = b"test_jwt"

        jwt = ingest_notifier.get_service_jwt()

        self.assertEqual(jwt, "test_jwt")
