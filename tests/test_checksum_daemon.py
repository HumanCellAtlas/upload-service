import sys, unittest, os
from unittest.mock import Mock, patch
import boto3, uuid
from moto import mock_s3

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from staging.checksum_daemon import ChecksumDaemon  # noqa
import staging.checksum_daemon.checksum_daemon  # noqa


class TestChecksumDaemon(unittest.TestCase):

    STAGING_BUCKET_NAME = os.environ['STAGING_S3_BUCKET']

    def setUp(self):
        # Setup mock AWS
        self.s3_mock = mock_s3()
        self.s3_mock.start()
        # Staging bucket
        self.staging_bucket = boto3.resource('s3').Bucket(self.STAGING_BUCKET_NAME)
        self.staging_bucket.create()
        # daemon
        context = Mock()
        self.daemon = ChecksumDaemon(context)
        # File
        self.area_id = str(uuid.uuid4())
        self.content_type = 'text/html'
        self.file_key = f"{self.area_id}/foo"
        self.staging_bucket.put_object(Key=self.file_key, Body="exquisite corpse", ContentType=self.content_type)
        self.event = {'Records': [
            {'eventVersion': '2.0', 'eventSource': 'aws:s3', 'awsRegion': 'us-east-1',
             'eventTime': '2017-09-15T00:05:10.378Z', 'eventName': 'ObjectCreated:Put',
             'userIdentity': {'principalId': 'AWS:AROAI4WRRXW2K3Y2IFL6Q:staging-api-dev'},
             'requestParameters': {'sourceIPAddress': '52.91.56.220'},
             'responseElements': {'x-amz-request-id': 'FEBC85CADD1E3A66',
                                  'x-amz-id-2': 'xxx'},
             's3': {'s3SchemaVersion': '1.0',
                    'configurationId': 'NGZjNmM0M2ItZTk0Yi00YTExLWE2NDMtMzYzY2UwN2EyM2Nj',
                    'bucket': {'name': self.STAGING_BUCKET_NAME,
                               'ownerIdentity': {'principalId': 'A29PZ5XRQWJUUM'},
                               'arn': 'arn:aws:s3:::org-humancellatlas-staging-dev'},
                    'object': {'key': self.file_key, 'size': 16,
                               'eTag': 'fea79d4ad9be6cf1c76a219bb735f85a',
                               'sequencer': '0059BB193641C4EAB0'}}}]}

    def tearDown(self):
        self.s3_mock.stop()

    @patch('staging.checksum_daemon.checksum_daemon.IngestNotifier.file_was_staged')
    def test_consume_event_sets_tags(self, mock_file_was_staged):

        self.daemon.consume_event(self.event)

        tagging = boto3.client('s3').get_object_tagging(Bucket=self.STAGING_BUCKET_NAME, Key=self.file_key)
        self.assertEqual(tagging['TagSet'], [
            {'Key': "hca-dss-content-type", 'Value': "text/html"},
            {'Key': "hca-dss-s3_etag", 'Value': "18f17fbfdd21cf869d664731e10d4ffd"},
            {'Key': "hca-dss-sha1", 'Value': "b1b101e21cf9cf8a4729da44d7818f935eec0ce8"},
            {'Key': "hca-dss-sha256", 'Value': "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70"},
            {'Key': "hca-dss-crc32c", 'Value': "FE9ADA52"}
        ])

    @patch('staging.checksum_daemon.checksum_daemon.IngestNotifier.file_was_staged')
    def test_consume_event_notifies_ingest(self, mock_file_was_staged):

        self.daemon.consume_event(self.event)

        self.assertTrue(mock_file_was_staged.called,
                        'IngestNotifier.file_was_staged should have been called')
        mock_file_was_staged.assert_called_once_with({
            'staging_area_id': self.area_id,
            'name': os.path.basename(self.file_key),
            'size': 16,
            'content_type': self.content_type,
            'url': f"s3://{self.STAGING_BUCKET_NAME}/{self.area_id}/foo",
            'checksums': {
                "s3_etag": "18f17fbfdd21cf869d664731e10d4ffd",
                "sha1": "b1b101e21cf9cf8a4729da44d7818f935eec0ce8",
                "sha256": "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70",
                "crc32c": "FE9ADA52"
            }
        })
