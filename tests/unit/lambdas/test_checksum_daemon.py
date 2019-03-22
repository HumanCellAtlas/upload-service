import os
import sys
import uuid
from unittest.mock import Mock, patch

import boto3
from sqlalchemy.orm.exc import NoResultFound

from upload.common.database_orm import DBSessionMaker, DbFile, DbChecksum
from upload.common.upload_area import UploadArea
from .. import UploadTestCaseUsingMockAWS, EnvironmentSetup
from ... import FixtureFile

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from upload.lambdas.checksum_daemon import ChecksumDaemon  # noqa


# Add checksums


class ChecksumDaemonTest(UploadTestCaseUsingMockAWS):

    def _make_dbfile(self, upload_area, test_file, checksums=None):
        return DbFile(s3_key=f"{upload_area.uuid}/{test_file.name}", s3_etag=test_file.e_tag,
                      upload_area_id=upload_area.db_id, name=test_file.name, size=test_file.size,
                      checksums=checksums)

    def setUp(self):
        super().setUp()
        # Environment
        self.environment = {
            'CSUM_DOCKER_IMAGE': 'bogoimage'
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()

        # Upload area
        self.area_uuid = str(uuid.uuid4())
        self.upload_area = UploadArea(self.area_uuid)
        self.upload_area.update_or_create()
        # daemon
        context = Mock()
        self.daemon = ChecksumDaemon(context)
        # File
        self.small_file = FixtureFile.factory('foo')
        self.file_key = f"{self.area_uuid}/{self.small_file.name}"
        self.object = self.upload_bucket.Object(self.file_key)
        self.object.put(Key=self.file_key, Body=self.small_file.contents, ContentType=self.small_file.content_type,
                        Metadata={'crc32c': self.small_file.crc32c})
        # Event
        self.events = {'Records': [
            {'eventVersion': '2.0', 'eventSource': 'aws:s3', 'awsRegion': 'us-east-1',
             'eventTime': '2017-09-15T00:05:10.378Z', 'eventName': 'ObjectCreated:Put',
             'userIdentity': {'principalId': 'AWS:AROAI4WRRXW2K3Y2IFL6Q:upload-api-dev'},
             'requestParameters': {'sourceIPAddress': '52.91.56.220'},
             'responseElements': {'x-amz-request-id': 'FEBC85CADD1E3A66',
                                  'x-amz-id-2': 'xxx'},
             's3': {'s3SchemaVersion': '1.0',
                    'configurationId': 'NGZjNmM0M2ItZTk0Yi00YTExLWE2NDMtMzYzY2UwN2EyM2Nj',
                    'bucket': {'name': self.upload_config.bucket_name,
                               'ownerIdentity': {'principalId': 'A29PZ5XRQWJUUM'},
                               'arn': f'arn:aws:s3:::{self.upload_config.bucket_name}'},
                    'object': {'key': self.file_key,
                               'size': self.small_file.size,
                               'eTag': self.small_file.e_tag,
                               'sequencer': '0059BB193641C4EAB0'}}}]}
        self.db_session_maker = DBSessionMaker()
        self.db = self.db_session_maker.session()


class TestChecksumDaemonSeeingS3ObjectsForTheFirstTime(ChecksumDaemonTest):
    """
    Scenario: a file is uploaded for the first time
    """

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_when_an_s3_object_is_seen_for_the_first_time__a_file_record_is_created(self,
                                                                                    mock_format_and_send_notification):
        with self.assertRaises(NoResultFound):
            self.db.query(DbFile).filter(DbFile.s3_key == self.file_key,
                                         DbFile.s3_etag == self.small_file.e_tag).one()

        self.daemon.consume_events(self.events)

        file_record = self.db.query(DbFile).filter(DbFile.s3_key == self.file_key,
                                                   DbFile.s3_etag == self.small_file.e_tag).one()

        self.assertEqual(self.upload_area.db_id, file_record.upload_area_id)
        self.assertEqual(self.small_file.name, file_record.name)
        self.assertEqual(self.small_file.size, file_record.size)

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_for_a_small_s3_object__csums_are_computed_in_the_lambda(self, mock_send_notif):
        self.daemon.consume_events(self.events)

        file_record = self.db.query(DbFile).filter(DbFile.s3_key == self.file_key,
                                                   DbFile.s3_etag == self.small_file.e_tag).one()
        self.assertEqual(self.small_file.checksums, file_record.checksums)

        tagging = boto3.client('s3').get_object_tagging(Bucket=self.upload_config.bucket_name, Key=self.file_key)
        self.assertEqual(self.small_file.s3_tagset, sorted(tagging['TagSet'], key=lambda x: x['Key']))

        checksum_record = self.db.query(DbChecksum).filter(DbChecksum.file_id == file_record.id).one()
        self.assertEqual("CHECKSUMMED", checksum_record.status)

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_when_a_small_s3_object_is_checksummed_inline_ingest_is_notified(self,
                                                                             mock_format_and_send_notification):
        self.daemon.consume_events(self.events)

        self.assertTrue(mock_format_and_send_notification.called,
                        'IngestNotifier.file_was_uploaded should have been called')

        mock_format_and_send_notification.assert_called_once_with({
            'upload_area_id': self.area_uuid,
            'name': os.path.basename(self.file_key),
            'size': 16,
            'last_modified': self.object.last_modified.isoformat(),
            'content_type': self.small_file.content_type,
            'url': f"s3://{self.upload_config.bucket_name}/{self.area_uuid}/{self.small_file.name}",
            'checksums': self.small_file.checksums
        })

    @patch('upload.common.upload_area.UploadedFile.size', 100 * 1024 * 1024 * 1024)
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon._enqueue_batch_job')
    def test_for_a_large_s3_object__a_checksumming_batch_job_is_scheduled(self, mock_enqueue_batch_job):
        mock_enqueue_batch_job.return_value = "fake-batch-job-id"
        file = self._make_dbfile(self.upload_area, self.small_file)  # note patch for .size above
        self.db.add(file)
        self.db.commit()

        self.daemon.consume_events(self.events)

        mock_enqueue_batch_job.assert_called()
        checksum_record = self.db.query(DbChecksum).filter(DbChecksum.file_id == file.id).one()
        self.assertEqual("SCHEDULED", checksum_record.status)
        self.assertEqual("fake-batch-job-id", checksum_record.job_id)


class TestChecksumDaemonSeeingS3ObjectsForWhichAFileRecordAlreadyExists(ChecksumDaemonTest):
    """
    Scenario: a file is re-uploaded using identical contents
    """

    def setUp(self):
        super().setUp()
        dbfile = self._make_dbfile(self.upload_area, self.small_file, checksums=self.small_file.checksums)
        self.db.add(dbfile)
        self.db.commit()

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_that_a_new_file_record_is_not_created(self, mock_fasn):
        record_count_before = self.db.query(DbFile).filter(DbFile.s3_key == self.file_key).count()

        self.daemon.consume_events(self.events)

        record_count_after = self.db.query(DbFile).filter(DbFile.s3_key == self.file_key).count()
        self.assertEqual(record_count_before, record_count_after)

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.DssChecksums.compute')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_when_the_file_record_contains_checksums__they_are_not_recomputed(self, mock_fasn, mock_compute):
        self.daemon.consume_events(self.events)

        mock_compute.assert_not_called()

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_when_the_file_record_contains_checksums__they_are_applied_as_tags(self, mock_fasn):
        self.daemon.consume_events(self.events)

        tagging = boto3.client('s3').get_object_tagging(Bucket=self.upload_config.bucket_name, Key=self.file_key)
        self.assertEqual(self.small_file.s3_tagset, sorted(tagging['TagSet'], key=lambda x: x['Key']))

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_when_the_file_is_tagged_ingest_is_notified(self, mock_format_and_send_notification):
        self.daemon.consume_events(self.events)

        self.assertTrue(mock_format_and_send_notification.called,
                        'IngestNotifier.file_was_uploaded should have been called')

        mock_format_and_send_notification.assert_called_once_with({
            'upload_area_id': self.area_uuid,
            'name': os.path.basename(self.file_key),
            'size': 16,
            'last_modified': self.object.last_modified.isoformat(),
            'content_type': self.small_file.content_type,
            'url': f"s3://{self.upload_config.bucket_name}/{self.area_uuid}/{self.small_file.name}",
            'checksums': self.small_file.checksums
        })
