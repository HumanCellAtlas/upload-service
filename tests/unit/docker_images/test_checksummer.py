import unittest
from unittest.mock import patch
import uuid

import boto3

from .. import UploadTestCaseUsingMockAWS, EnvironmentSetup
from ... import FIXTURE_DATA_CHECKSUMS

# pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docker-images', 'checksummer'))  # noqa
# sys.path.insert(0, pkg_root)  # noqa

from upload.docker_images.checksummer.checksummer import Checksummer
from upload.common.upload_area import UploadArea
from upload.common.upload_config import UploadConfig


class TestChecksummerDockerImage(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        UploadConfig.use_env = True
        # Setup environment
        self.upload_bucket_name = 'bogobucket'
        self.checksum_id = str(uuid.uuid4())
        self.environment = {
            'BUCKET_NAME': self.upload_bucket_name,
            'AWS_BATCH_JOB_ID': '1',
            'INGEST_AMQP_SERVER': 'bogoamqp',
            'CHECKSUM_ID': self.checksum_id
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()
        self.upload_area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.upload_area_id)
        self.upload_area.update_or_create()

    def tearDown(self):
        super().tearDown()
        self.environmentor.exit()

    @patch('upload.docker_images.checksummer.checksummer.update_event')
    def test_checksummer_checksums(self, mock_update_checksum_event):
        filename = "foo"
        file_contents = "exquisite corpse"
        file_s3_key = f"{self.upload_area_id}/{filename}"
        self.mock_upload_file_to_s3(self.upload_area_id, filename, contents=file_contents,
                                    content_type='application/json; dcp_type=metadata',
                                    checksums={})
        s3_url = f"s3://{self.upload_bucket_name}/{file_s3_key}"

        Checksummer([s3_url])

        tagging = boto3.client('s3').get_object_tagging(Bucket=self.upload_bucket_name, Key=file_s3_key)
        self.assertEqual(
            sorted(tagging['TagSet'], key=lambda x: x['Key']),
            sorted(FIXTURE_DATA_CHECKSUMS[file_contents]['s3_tagset'], key=lambda x: x['Key'])
        )


if __name__ == '__main__':
    unittest.main()
