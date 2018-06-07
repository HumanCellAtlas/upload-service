from datetime import datetime, timedelta
import os
import sys
from unittest.mock import Mock, patch
import uuid

import boto3

from .. import UploadTestCaseUsingMockAWS, EnvironmentSetup
from ... import FIXTURE_DATA_CHECKSUMS

from upload.common.upload_area import UploadArea
from upload.common.upload_config import UploadConfig
from upload.common.database_orm import db_session_maker, DbFile, DbChecksum

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from upload.lambdas.checksum_daemon import ChecksumDaemon  # noqa


class TestChecksumDaemon(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        # Config
        self.config = UploadConfig()
        self.config.set({
            'bucket_name': 'bogo_bucket',
            'csum_job_q_arn': 'bogo_arn',
            'csum_job_role_arn': 'bogo_role_arn',
        })
        # Environment
        self.environment = {
            'DEPLOYMENT_STAGE': 'test',
            'INGEST_AMQP_SERVER': 'foo',
            'CSUM_DOCKER_IMAGE': 'bogoimage'
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()

        # Staging bucket
        self.upload_bucket = boto3.resource('s3').Bucket(self.config.bucket_name)
        self.upload_bucket.create()
        # Upload area
        self.area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.area_id)
        self.upload_area.create()
        # daemon
        context = Mock()
        self.daemon = ChecksumDaemon(context)
        # File
        self.content_type = 'text/html'
        self.filename = 'foo'
        self.file_key = f"{self.area_id}/{self.filename}"
        self.file_contents = "exquisite corpse"
        self.object = self.upload_bucket.Object(self.file_key)
        self.object.put(Key=self.file_key, Body=self.file_contents, ContentType=self.content_type)
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
                    'bucket': {'name': self.config.bucket_name,
                               'ownerIdentity': {'principalId': 'A29PZ5XRQWJUUM'},
                               'arn': f'arn:aws:s3:::{self.config.bucket_name}'},
                    'object': {'key': self.file_key, 'size': 16,
                               'eTag': 'fea79d4ad9be6cf1c76a219bb735f85a',
                               'sequencer': '0059BB193641C4EAB0'}}}]}

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon._checksum_file')
    def test_that_if_the_file_has_not_been_checksummed_it_will_be_checksummed(self, mock_checksum_file):

        self.daemon.consume_event(self.event)

        mock_checksum_file.assert_called()

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.connect')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_that_if_a_small_file_has_not_been_checksummed_it_is_checksummed_inline(self,
                                                                                    mock_format_and_send_notification,
                                                                                    mock_connect):
            self.daemon.consume_event(self.event)

            tagging = boto3.client('s3').get_object_tagging(Bucket=self.config.bucket_name, Key=self.file_key)
            self.assertEqual(
                sorted(tagging['TagSet'], key=lambda x: x['Key']),
                sorted(FIXTURE_DATA_CHECKSUMS[self.file_contents]['s3_tagset'], key=lambda x: x['Key'])
            )

            session = db_session_maker()
            db_checksum = session.query(DbChecksum).filter(DbChecksum.file_id == self.file_key).one()
            self.assertEqual(FIXTURE_DATA_CHECKSUMS[self.file_contents]['checksums'], db_checksum.checksums)

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.connect')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_when_a_small_is_checksummed_inline_ingest_is_notified(self,
                                                                   mock_format_and_send_notification,
                                                                   mock_connect):
        self.daemon.consume_event(self.event)

        self.assertTrue(mock_connect.called, 'IngestNotifier.connect should have been called')
        self.assertTrue(mock_format_and_send_notification.called,
                        'IngestNotifier.file_was_uploaded should have been called')
        mock_format_and_send_notification.assert_called_once_with({
            'upload_area_id': self.area_id,
            'name': os.path.basename(self.file_key),
            'size': 16,
            'last_modified': self.object.last_modified.isoformat(),
            'content_type': self.content_type,
            'url': f"s3://{self.config.bucket_name}/{self.area_id}/{self.filename}",
            'checksums': FIXTURE_DATA_CHECKSUMS[self.file_contents]['checksums']
        })

    @patch('upload.common.upload_area.UploadedFile.size', 100 * 1024 * 1024 * 1024)
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon._schedule_checksumming')
    def test_when_a_large_file_has_not_been_checksummed_a_batch_job_is_scheduled(self, mock_schedule_checksumming):
        session = db_session_maker()
        file = DbFile(id=self.file_key, upload_area_id=self.upload_area.uuid, name=self.filename, size=123)
        checksum_time = self.object.last_modified - timedelta(minutes=5)
        checksum = DbChecksum(id=str(uuid.uuid4()), file_id=self.file_key, status='CHECKSUMMED',
                              checksum_started_at=checksum_time, checksum_ended_at=checksum_time,
                              updated_at=checksum_time)
        session.add(file)
        session.add(checksum)
        session.commit()

        self.daemon.consume_event(self.event)

        mock_schedule_checksumming.assert_called()

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon._checksum_file')
    def test_if_the_file_has_been_summed_since_last_change_it_is_not_summed_again(self, mock_checksum_file):
        session = db_session_maker()
        file = DbFile(id=self.file_key, upload_area_id=self.upload_area.uuid, name=self.filename, size=123)
        checksum_time = datetime.utcnow() + timedelta(minutes=5)
        checksum = DbChecksum(id=str(uuid.uuid4()), file_id=self.file_key, status='CHECKSUMMED',
                              checksum_started_at=checksum_time, checksum_ended_at=checksum_time,
                              updated_at=checksum_time)
        session.add(file)
        session.add(checksum)
        session.commit()

        self.daemon.consume_event(self.event)

        mock_checksum_file.assert_not_called()
