from datetime import datetime, timedelta
import os
import sys
from unittest.mock import Mock, patch
import uuid

import boto3

from .. import UploadTestCaseUsingMockAWS, EnvironmentSetup
from ... import FixtureFile

from upload.common.upload_area import UploadArea
from upload.common.database_orm import DBSessionMaker, DbFile, DbChecksum

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from upload.lambdas.checksum_daemon import ChecksumDaemon  # noqa


class TestChecksumDaemon(UploadTestCaseUsingMockAWS):

    def _make_dbfile(self, upload_area, test_file):
        return DbFile(s3_key=f"{upload_area.uuid}/{test_file.name}", s3_etag=test_file.e_tag,
                      upload_area_id=upload_area.db_id, name=test_file.name, size=test_file.size)

    def setUp(self):
        super().setUp()
        # Environment
        self.environment = {
            'INGEST_AMQP_SERVER': 'foo',
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
        self.test_file = FixtureFile.factory('foo')
        self.file_key = f"{self.area_uuid}/{self.test_file.name}"
        self.object = self.upload_bucket.Object(self.file_key)
        self.object.put(Key=self.file_key, Body=self.test_file.contents, ContentType=self.test_file.content_type)
        # Event
        self.event = {'Records': [
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
                    'object': {'key': self.file_key, 'size': 16,
                               'eTag': self.test_file.e_tag,
                               'sequencer': '0059BB193641C4EAB0'}}}]}
        self.db_session_maker = DBSessionMaker()

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon._checksum_file')
    def test_that_if_the_file_has_not_been_checksummed_it_will_be_checksummed(self, mock_checksum_file):

        self.daemon.consume_event(self.event)

        mock_checksum_file.assert_called()

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon.CHECK_CONTENT_TYPE_TIMES', 0)
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_that_if_a_small_file_has_not_been_checksummed_it_is_checksummed_inline(self,
                                                                                    mock_format_and_send_notification):
            self.daemon.consume_event(self.event)

            tagging = boto3.client('s3').get_object_tagging(Bucket=self.upload_config.bucket_name, Key=self.file_key)
            self.assertEqual(
                sorted(tagging['TagSet'], key=lambda x: x['Key']),
                self.test_file.s3_tagset
            )

            session = self.db_session_maker.session()
            file = self.upload_area.uploaded_file(self.test_file.name)
            db_checksum = session.query(DbChecksum).filter(DbChecksum.file_id == file.db_id).one()
            self.assertEqual(self.test_file.checksums, db_checksum.checksums)

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon.CHECK_CONTENT_TYPE_TIMES', 0)
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_when_a_small_is_checksummed_inline_ingest_is_notified(self,
                                                                   mock_format_and_send_notification):
        self.daemon.consume_event(self.event)

        self.assertTrue(mock_format_and_send_notification.called,
                        'IngestNotifier.file_was_uploaded should have been called')
        mock_format_and_send_notification.assert_called_once_with({
            'upload_area_id': self.area_uuid,
            'name': os.path.basename(self.file_key),
            'size': 16,
            'last_modified': self.object.last_modified.isoformat(),
            'content_type': self.test_file.content_type,
            'url': f"s3://{self.upload_config.bucket_name}/{self.area_uuid}/{self.test_file.name}",
            'checksums': self.test_file.checksums
        })

    @patch('upload.common.upload_area.UploadedFile.size', 100 * 1024 * 1024 * 1024)
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon._schedule_checksumming')
    def test_when_a_large_file_has_not_been_checksummed_a_batch_job_is_scheduled(self, mock_schedule_checksumming):
        session = self.db_session_maker.session()
        file = self._make_dbfile(self.upload_area, self.test_file)
        session.add(file)
        session.commit()
        checksum_time = self.object.last_modified - timedelta(minutes=5)
        checksum = DbChecksum(id=str(uuid.uuid4()), file_id=file.id, status='CHECKSUMMED',
                              checksum_started_at=checksum_time, checksum_ended_at=checksum_time,
                              updated_at=checksum_time)
        session.add(checksum)
        session.commit()

        self.daemon.consume_event(self.event)

        mock_schedule_checksumming.assert_called()

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon.CHECK_CONTENT_TYPE_TIMES', 0)
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon._checksum_file')
    def test_if_the_file_has_been_summed_since_last_change_it_is_not_summed_again(self, mock_checksum_file,
                                                                                  mock_format_and_send_notification):
        session = self.db_session_maker.session()
        file = self._make_dbfile(self.upload_area, self.test_file)
        session.add(file)
        session.commit()
        checksum_time = datetime.utcnow() + timedelta(minutes=5)
        checksum = DbChecksum(id=str(uuid.uuid4()), file_id=file.id, status='CHECKSUMMING',
                              checksum_started_at=checksum_time, checksum_ended_at=checksum_time,
                              updated_at=checksum_time)
        session.add(checksum)
        session.commit()

        self.daemon.consume_event(self.event)

        mock_checksum_file.assert_not_called()

        self.assertFalse(mock_format_and_send_notification.called,
                         'IngestNotifier.file_was_uploaded should not have been called')

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon.CHECK_CONTENT_TYPE_TIMES', 0)
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon._checksum_file')
    def test_if_the_file_has_not_been_summed_since_last_change_it_is_summed_again(self, mock_checksum_file,
                                                                                  mock_format_and_send_notification):
        session = self.db_session_maker.session()
        file = self._make_dbfile(self.upload_area, self.test_file)
        session.add(file)
        session.commit()
        checksum_time = datetime.utcnow() + timedelta(minutes=5)
        checksum = DbChecksum(id=str(uuid.uuid4()), file_id=file.id, status='CHECKSUMMED',
                              checksum_started_at=checksum_time, checksum_ended_at=checksum_time,
                              updated_at=checksum_time)
        session.add(checksum)
        session.commit()

        self.daemon.consume_event(self.event)

        mock_checksum_file.assert_not_called()

        self.assertTrue(mock_format_and_send_notification.called,
                        'IngestNotifier.file_was_uploaded should have been called')
