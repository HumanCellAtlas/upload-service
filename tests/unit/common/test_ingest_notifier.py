import uuid
from unittest.mock import patch

from upload.common.database import UploadDB
from upload.common.ingest_notifier import IngestNotifier
from upload.common.upload_area import UploadArea
from .. import UploadTestCaseUsingMockAWS


class TestIngestNotifier(UploadTestCaseUsingMockAWS):

    def test__init__creates_urls_for_files(self):
        ingest_notifier_one = IngestNotifier("file_uploaded", file_id=None)
        ingest_notifier_two = IngestNotifier("file_validated", file_id=None)

        expected_url_for_one = "https://test_ingest_api_host/messaging/fileUploadInfo"
        expected_url_for_two = "https://test_ingest_api_host/messaging/fileValidationResult"

        self.assertEqual(ingest_notifier_one.ingest_notification_url, expected_url_for_one)
        self.assertEqual(ingest_notifier_two.ingest_notification_url, expected_url_for_two)

    def test__ingest_api_host__successful(self):
        ingest_notifier = IngestNotifier("file_uploaded", file_id=None)
        ingest_api_host = ingest_notifier.ingest_api_host
        self.assertEqual(ingest_api_host, "test_ingest_api_host")

    def test__dcp_auth0_audience__successful(self):
        ingest_notifier = IngestNotifier("file_uploaded", file_id=None)
        dcp_auth0_audience = ingest_notifier.dcp_auth0_audience
        self.assertEqual(dcp_auth0_audience, "test_dcp_auth0_audience")

    def test__gcp_service_acct_creds__successful(self):
        ingest_notifier = IngestNotifier("file_uploaded", file_id=None)

        gcp_service_acct_creds = ingest_notifier.gcp_service_acct_creds

        self.assertEqual(gcp_service_acct_creds["private_key"], "test_private_key")
        self.assertEqual(gcp_service_acct_creds["private_key_id"], "test_private_key_id")
        self.assertEqual(gcp_service_acct_creds["client_email"], "test_client_email")

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier._send_notification')
    def test__format_and_send_notification__creates_pg_record_successfully(self, mock_send_notification):
        area_uuid = str(uuid.uuid4())
        upload_area = UploadArea(area_uuid)
        upload_area.update_or_create()
        upload_area._db_load()
        file = upload_area.store_file("test_file_name", "test_file_content", "application/json; dcp-type=data")
        ingest_notifier = IngestNotifier("file_uploaded", file_id=file.db_id)

        test_payload = {'names': "[test_file_name]", 'upload_area_id': area_uuid}
        notification_id = ingest_notifier.format_and_send_notification(test_payload)

        record = UploadDB().get_pg_record("notification", notification_id, column="id")
        self.assertEqual(record['status'], "DELIVERED")
        self.assertEqual(record['file_id'], file.db_id)
        self.assertEqual(record['payload'], test_payload)

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier._send_notification')
    def test__format_and_send_notification__dev_doesnt_trigger_notification(self, mock_send_notification):
        """ Upload areas that begin with deadbeef indicate that these are test environments so do not notify ingest."""
        area_uuid = "deadbeef" + str(uuid.uuid4())
        upload_area = UploadArea(area_uuid)
        upload_area.update_or_create()
        upload_area._db_load()
        file = upload_area.store_file("test_file_name", "test_file_content", "application/json; dcp-type=data")
        ingest_notifier = IngestNotifier("file_uploaded", file_id=file.db_id)

        test_payload = {'names': "[test_file_name]", 'upload_area_id': area_uuid}
        notification_id = ingest_notifier.format_and_send_notification(test_payload)

        self.assertIsNone(notification_id)

    @patch('upload.common.ingest_notifier.encode')
    def test__get_service_jwt__successful(self, mock_encode):
        ingest_notifier = IngestNotifier("file_uploaded", file_id=None)
        mock_encode.return_value = b"test_jwt"

        jwt = ingest_notifier.get_service_jwt()

        self.assertEqual(jwt, "test_jwt")
