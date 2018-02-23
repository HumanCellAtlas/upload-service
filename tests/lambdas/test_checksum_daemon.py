import sys
import unittest
import os
from unittest.mock import Mock, patch
import uuid

import boto3
from moto import mock_s3, mock_sns, mock_sts

from .. import EnvironmentSetup, FIXTURE_DATA_CHECKSUMS

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa


class TestChecksumDaemon(unittest.TestCase):

    DEPLOYMENT_STAGE = 'test'
    UPLOAD_BUCKET_NAME = 'bogobucket'

    def setUp(self):
        # Setup mock AWS
        self.s3_mock = mock_s3()
        self.s3_mock.start()
        self.sns_mock = mock_sns()
        self.sns_mock.start()
        self.sts_mock = mock_sts()
        self.sts_mock.start()
        # Staging bucket
        self.upload_bucket = boto3.resource('s3').Bucket(self.UPLOAD_BUCKET_NAME)
        self.upload_bucket.create()
        # Setup SNS
        boto3.resource('sns').create_topic(Name='bogotopic')
        # daemon
        context = Mock()
        self.environment = {
            'BUCKET_NAME': self.UPLOAD_BUCKET_NAME,
            'DEPLOYMENT_STAGE': self.DEPLOYMENT_STAGE,
            'INGEST_AMQP_SERVER': 'foo',
            'DCP_EVENTS_TOPIC': 'bogotopic',
            'CSUM_USE_BATCH_FILE_SIZE_THRESHOLD_GB': '4',
            'CSUM_JOB_Q_ARN': 'bogoqarn',
            'CSUM_JOB_ROLE_ARN': 'bogorolearn',
            'CSUM_DOCKER_IMAGE': 'bogoimage'
        }
        with EnvironmentSetup(self.environment):
            from upload.lambdas.checksum_daemon import ChecksumDaemon
            self.daemon = ChecksumDaemon(context)
        # File
        self.area_id = str(uuid.uuid4())
        self.content_type = 'text/html'
        self.filename = 'foo'
        self.file_key = f"{self.area_id}/{self.filename}"
        self.file_contents = "exquisite corpse"
        self.object = self.upload_bucket.Object(self.file_key)
        self.object.put(Key=self.file_key, Body=self.file_contents, ContentType=self.content_type)
        self.event = {'Records': [
            {'eventVersion': '2.0', 'eventSource': 'aws:s3', 'awsRegion': 'us-east-1',
             'eventTime': '2017-09-15T00:05:10.378Z', 'eventName': 'ObjectCreated:Put',
             'userIdentity': {'principalId': 'AWS:AROAI4WRRXW2K3Y2IFL6Q:upload-api-dev'},
             'requestParameters': {'sourceIPAddress': '52.91.56.220'},
             'responseElements': {'x-amz-request-id': 'FEBC85CADD1E3A66',
                                  'x-amz-id-2': 'xxx'},
             's3': {'s3SchemaVersion': '1.0',
                    'configurationId': 'NGZjNmM0M2ItZTk0Yi00YTExLWE2NDMtMzYzY2UwN2EyM2Nj',
                    'bucket': {'name': self.UPLOAD_BUCKET_NAME,
                               'ownerIdentity': {'principalId': 'A29PZ5XRQWJUUM'},
                               'arn': f'arn:aws:s3:::{self.UPLOAD_BUCKET_NAME}'},
                    'object': {'key': self.file_key, 'size': 16,
                               'eTag': 'fea79d4ad9be6cf1c76a219bb735f85a',
                               'sequencer': '0059BB193641C4EAB0'}}}]}

    def tearDown(self):
        self.s3_mock.stop()
        self.sns_mock.stop()
        self.sts_mock.stop()

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.connect')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.file_was_uploaded')
    def test_consume_event_sets_tags(self, mock_file_was_uploaded, mock_connect):

        with EnvironmentSetup(self.environment):
            self.daemon.consume_event(self.event)

        tagging = boto3.client('s3').get_object_tagging(Bucket=self.UPLOAD_BUCKET_NAME, Key=self.file_key)
        self.assertEqual(
            sorted(tagging['TagSet'], key=lambda x: x['Key']),
            sorted(FIXTURE_DATA_CHECKSUMS[self.file_contents]['s3_tagset'], key=lambda x: x['Key'])
        )

    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.connect')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.file_was_uploaded')
    def test_consume_event_notifies_ingest(self, mock_file_was_uploaded, mock_connect):

        with EnvironmentSetup(self.environment):
            self.daemon.consume_event(self.event)

        self.assertTrue(mock_connect.called,
                        'IngestNotifier.connect should have been called')
        self.assertTrue(mock_file_was_uploaded.called,
                        'IngestNotifier.file_was_uploaded should have been called')
        mock_file_was_uploaded.assert_called_once_with({
            'upload_area_id': self.area_id,
            'name': os.path.basename(self.file_key),
            'size': 16,
            'last_modified': self.object.last_modified.isoformat(),
            'content_type': self.content_type,
            'url': f"s3://{self.UPLOAD_BUCKET_NAME}/{self.area_id}/{self.filename}",
            'checksums': FIXTURE_DATA_CHECKSUMS[self.file_contents]['checksums']
        })

    @patch('upload.common.upload_area.UploadedFile.size', 100 * 1024 * 1024 * 1024)
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon.schedule_checksumming')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.connect')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.file_was_uploaded')
    def test_that_with_a_large_file_a_batch_job_is_scheduled(self,
                                                             mock_file_was_uploaded,
                                                             mock_connect,
                                                             mock_schedule_checksumming):
        with EnvironmentSetup(self.environment):
            self.daemon.consume_event(self.event)

        mock_schedule_checksumming.assert_called()
