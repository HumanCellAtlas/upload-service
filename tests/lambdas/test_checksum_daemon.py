import sys
import os
from unittest.mock import Mock, patch
import uuid

import boto3

from .. import UploadTestCaseUsingMockAWS, EnvironmentSetup
from upload.common.upload_area import UploadArea

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from upload.lambdas.checksum_daemon import ChecksumDaemon  # noqa


class TestChecksumDaemon(UploadTestCaseUsingMockAWS):

    DEPLOYMENT_STAGE = 'test'
    UPLOAD_BUCKET_NAME = 'bogobucket'

    @patch('upload.common.upload_area.UploadArea.IAM_SETTLE_TIME_SEC', 0)
    def setUp(self):
        super().setUp()
        # Environment
        self.environment = {
            'BUCKET_NAME': self.UPLOAD_BUCKET_NAME,
            'DEPLOYMENT_STAGE': self.DEPLOYMENT_STAGE,
            'INGEST_AMQP_SERVER': 'foo',
            'DCP_EVENTS_TOPIC': 'bogotopic',
            'CSUM_JOB_Q_ARN': 'bogoqarn',
            'CSUM_JOB_ROLE_ARN': 'bogorolearn',
            'CSUM_DOCKER_IMAGE': 'bogoimage'
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()
        # Staging bucket
        self.upload_bucket = boto3.resource('s3').Bucket(self.UPLOAD_BUCKET_NAME)
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

    @patch('upload.common.upload_area.UploadedFile.size', 100 * 1024 * 1024 * 1024)
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.ChecksumDaemon.schedule_checksumming')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.connect')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_that_with_a_large_file_a_batch_job_is_scheduled(self,
                                                             mock_format_and_send_notification,
                                                             mock_connect,
                                                             mock_schedule_checksumming):
        self.daemon.consume_event(self.event)

        mock_schedule_checksumming.assert_called()
