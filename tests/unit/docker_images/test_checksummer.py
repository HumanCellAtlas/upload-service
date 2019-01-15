import unittest
from unittest.mock import patch
import uuid

import boto3

from .. import UploadTestCaseUsingMockAWS, EnvironmentSetup
from ... import FIXTURE_DATA_CHECKSUMS

from upload.common.upload_config import UploadConfig


class TestChecksummerDockerImage(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        UploadConfig.use_env = True
        # Setup environment
        self.environment = {
            'BUCKET_NAME': self.upload_bucket.name,
            'AWS_BATCH_JOB_ID': '1',
            'INGEST_AMQP_SERVER': 'bogoamqp',
            'API_HOST': 'bogohost',
            'CHECKSUM_ID': str(uuid.uuid4()),
            'CONTAINER': 'yes'
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()

    def tearDown(self):
        super().tearDown()
        self.environmentor.exit()

    @patch('upload.docker_images.checksummer.checksummer.update_event')
    def test_checksummer_checksums(self, mock_update_checksum_event):
        file_s3_key = "somearea/foo"
        file_contents = "exquisite corpse"
        self.create_s3_object(file_s3_key, content=file_contents)
        s3_url = f"s3://{self.upload_bucket.name}/{file_s3_key}"

        from upload.docker_images.checksummer.checksummer import Checksummer
        Checksummer([s3_url])

        tagging = boto3.client('s3').get_object_tagging(Bucket=self.upload_bucket.name, Key=file_s3_key)
        self.assertEqual(
            sorted(tagging['TagSet'], key=lambda x: x['Key']),
            sorted(FIXTURE_DATA_CHECKSUMS[file_contents]['s3_tagset'], key=lambda x: x['Key'])
        )


if __name__ == '__main__':
    unittest.main()
