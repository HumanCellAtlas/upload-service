import uuid
from unittest.mock import patch

from upload.common.database_orm import DBSessionMaker, DbChecksum, DbFile
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

        self.db = DBSessionMaker().session()

        # Authentication
        self.authentication_header = {'Api-Key': self.api_key}
        # Setup app
        self.client = client_for_test_api_server()

    def tearDown(self):
        super().tearDown()
        self.environmentor.exit()

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_get_checksum__for_a_file_with_no_checksum_records__returns_status_unscheduled(self, mock_fasn):
        db_area = self.create_upload_area()
        upload_area = UploadArea(db_area.uuid)
        s3obj = self.mock_upload_file_to_s3(upload_area.uuid, 'foo.json')
        UploadedFile(upload_area, s3object=s3obj)  # creates file record

        response = self.client.get(f"/v1/area/{upload_area.uuid}/foo.json/checksum")

        checksum_status = response.get_json()['checksum_status']
        self.assertEqual("UNSCHEDULED", checksum_status)

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_get_checksum__for_a_file_with_checksum_records__returns_the_most_recent_record_status(self, mock_fasn):
        checksum_id = str(uuid.uuid4())
        db_area = self.create_upload_area()
        upload_area = UploadArea(db_area.uuid)
        s3obj = self.mock_upload_file_to_s3(upload_area.uuid, 'foo.json')
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        checksum_event = ChecksumEvent(file_id=uploaded_file.db_id,
                                       checksum_id=checksum_id,
                                       job_id='12345',
                                       status="SCHEDULED")
        checksum_event.create_record()

        response = self.client.get(f"/v1/area/{upload_area.uuid}/{uploaded_file.name}/checksum")

        info = response.get_json()
        self.assertEqual("SCHEDULED", info['checksum_status'])
        self.assertEqual(uploaded_file.checksums, info['checksums'])

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_post_checksum__with_a_checksumming_payload__updates_db_record(self, mock_format_and_send_notification):
        checksum_id = str(uuid.uuid4())
        db_area = self.create_upload_area()
        upload_area = UploadArea(db_area.uuid)
        s3obj = self.mock_upload_file_to_s3(upload_area.uuid, 'foo.json')
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        checksum_event = ChecksumEvent(file_id=uploaded_file.db_id,
                                       checksum_id=checksum_id,
                                       job_id='12345',
                                       status="SCHEDULED")
        checksum_event.create_record()

        response = self.client.post(f"/v1/area/{upload_area.uuid}/update_checksum/{checksum_id}",
                                    headers=self.authentication_header,
                                    json={
                                        "status": "CHECKSUMMING",
                                        "job_id": checksum_event.job_id,
                                        "payload": uploaded_file.info()
                                    })

        self.assertEqual(204, response.status_code)
        db_checksum = self.db.query(DbChecksum).filter(DbChecksum.id == checksum_id).one()
        self.assertEqual("CHECKSUMMING", db_checksum.status)

        mock_format_and_send_notification.assert_not_called()

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_post_checksum__with_a_checksummed_payload__updates_db_records_and_notifies_ingest(self, mock_fasn):
        checksum_id = str(uuid.uuid4())
        db_area = self.create_upload_area()
        upload_area = UploadArea(db_area.uuid)
        s3obj = self.mock_upload_file_to_s3(upload_area.uuid, 'foo.json')
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        checksum_event = ChecksumEvent(file_id=uploaded_file.db_id,
                                       checksum_id=checksum_id,
                                       job_id='12345',
                                       status="SCHEDULED")
        checksum_event.create_record()
        checksums = {'crc32c': 'w', 's3_etag': 'x', 'sha1': 'y', 'sha256': 'z'}
        response = self.client.post(f"/v1/area/{upload_area.uuid}/update_checksum/{checksum_id}",
                                    headers=self.authentication_header,
                                    json={
                                        "status": "CHECKSUMMED",
                                        "job_id": checksum_event.job_id,
                                        "payload": {
                                            "upload_area_id": upload_area.db_id,
                                            "name": uploaded_file.name,
                                            "checksums": checksums
                                        }
                                    })

        self.assertEqual(204, response.status_code)

        # Checksum record status should be updated
        db_checksum = self.db.query(DbChecksum).filter(DbChecksum.id == checksum_id).one()
        self.assertEqual("CHECKSUMMED", db_checksum.status)

        # Checksums should be stored in File record
        db_file = self.db.query(DbFile).filter(DbFile.id == uploaded_file.db_id).one()
        self.assertEqual(checksums, db_file.checksums)

        # Ingest should be notified
        mock_fasn.assert_called()

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_checksum_statuses_for_upload_area(self, mock_format_and_send_notification):
        db_area = self.create_upload_area()
        upload_area = UploadArea(db_area.uuid)

        checksum1_id = str(uuid.uuid4())
        checksum2_id = str(uuid.uuid4())
        checksum3_id = str(uuid.uuid4())

        s3obj1 = self.mock_upload_file_to_s3(upload_area.uuid, 'foo1.json')
        s3obj2 = self.mock_upload_file_to_s3(upload_area.uuid, 'foo2.json')
        s3obj3 = self.mock_upload_file_to_s3(upload_area.uuid, 'foo3.json')
        s3obj4 = self.mock_upload_file_to_s3(upload_area.uuid, 'foo4.json')
        s3obj5 = self.mock_upload_file_to_s3(upload_area.uuid, 'foo5.json')

        f1 = UploadedFile(upload_area, s3object=s3obj1)
        f2 = UploadedFile(upload_area, s3object=s3obj2)
        f3 = UploadedFile(upload_area, s3object=s3obj3)
        UploadedFile(upload_area, s3object=s3obj4)
        UploadedFile(upload_area, s3object=s3obj5)

        checksum1_event = ChecksumEvent(file_id=f1.db_id, checksum_id=checksum1_id, job_id='123', status="SCHEDULED")
        checksum2_event = ChecksumEvent(file_id=f2.db_id, checksum_id=checksum2_id, job_id='456', status="CHECKSUMMING")
        checksum3_event = ChecksumEvent(file_id=f3.db_id, checksum_id=checksum3_id, job_id='789', status="CHECKSUMMED")
        checksum1_event.create_record()
        checksum2_event.create_record()
        checksum3_event.create_record()

        response = self.client.get(f"/v1/area/{upload_area.uuid}/checksums")
        expected_data = {
            'CHECKSUMMED': 1,
            'CHECKSUMMING': 1,
            'CHECKSUMMING_UNSCHEDULED': 2,
            'SCHEDULED': 1,
            'TOTAL_NUM_FILES': 5
        }

        assert response.get_json() == expected_data
