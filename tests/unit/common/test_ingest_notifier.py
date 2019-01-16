import uuid

from unittest.mock import patch

from upload.common.ingest_notifier import IngestNotifier
from upload.common.upload_area import UploadArea
from upload.common.database import UploadDB
from ..lambdas.api_server import client_for_test_api_server
from .. import UploadTestCaseUsingMockAWS


class TestIngestNotifier(UploadTestCaseUsingMockAWS):

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

    def test_dcp_auth0_audience(self):
        ingest_notifier = IngestNotifier("file_uploaded")
        dcp_auth0_audience = ingest_notifier.dcp_auth0_audience
        self.assertEqual(dcp_auth0_audience, "test_dcp_auth0_audience")

    def test_gcp_service_acct_creds(self):
        ingest_notifier = IngestNotifier("file_uploaded")

        gcp_service_acct_creds = ingest_notifier.gcp_service_acct_creds

        self.assertEqual(gcp_service_acct_creds["private_key"], "test_private_key")
        self.assertEqual(gcp_service_acct_creds["private_key_id"], "test_private_key_id")
        self.assertEqual(gcp_service_acct_creds["client_email"], "test_client_email")

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier._send_notification')
    def test_format_and_send_notification(self, mock_send_notification):
        ingest_notifier = IngestNotifier("file_uploaded")
        area_uuid = str(uuid.uuid4())
        upload_area = UploadArea(area_uuid)
        upload_area.update_or_create()
        upload_area._db_load()
        upload_area.store_file("test_file_name", "test_file_content", "application/json; dcp-type=data")

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
