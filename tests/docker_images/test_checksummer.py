import sys
import unittest
import os
from unittest.mock import patch
import uuid
import boto3
from moto import mock_s3, mock_iam, mock_sns, mock_sts

from .. import EnvironmentSetup, FIXTURE_DATA_CHECKSUMS

# pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docker-images', 'checksummer'))  # noqa
# sys.path.insert(0, pkg_root)  # noqa

from upload.docker_images.checksummer.checksummer import Checksummer
from upload.common.upload_area import UploadArea


class TestChecksummerDockerImage(unittest.TestCase):

    @patch('upload.common.upload_area.UploadArea.IAM_SETTLE_TIME_SEC', 0)
    def setUp(self):
        # Setup mock AWS
        self.s3_mock = mock_s3()
        self.s3_mock.start()
        self.sns_mock = mock_sns()
        self.sns_mock.start()
        self.sts_mock = mock_sts()
        self.sts_mock.start()
        self.iam_mock = mock_iam()
        self.iam_mock.start()

        # Setup upload bucket
        self.deployment_stage = 'test'
        self.upload_bucket_name = f'bogobucket'
        self.upload_bucket = boto3.resource('s3').Bucket(self.upload_bucket_name)
        self.upload_bucket.create()
        self.environment = {
            'BUCKET_NAME': self.upload_bucket_name,
            'DEPLOYMENT_STAGE': self.deployment_stage,
            'DCP_EVENTS_TOPIC': 'bogotopic',
            'AWS_BATCH_JOB_ID': '1',
            'INGEST_AMQP_SERVER': 'bogoamqp'
        }
        self.upload_area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.upload_area_id)
        self.upload_area.create()
        self.checksum_id = str(uuid.uuid4())

    def tearDown(self):
        self.s3_mock.stop()
        self.sns_mock.stop()
        self.sts_mock.stop()
        self.iam_mock.stop()

    def _mock_upload_file(self, filename, contents="foo",
                          content_type='application/json; dcp_type=metadata', checksums=None):
        tag_set = [
            {'Key': 'hca-dss-content-type', 'Value': content_type},
        ]
        if checksums:
            for csum_type, csum_value in checksums.items():
                tag_set.append({'Key': f"hca-dss-{csum_type}", 'Value': csum_value})

        file_key = f"{self.upload_area_id}/{filename}"
        s3obj = self.upload_bucket.Object(file_key)
        s3obj.put(Body=contents, ContentType=content_type)
        boto3.client('s3').put_object_tagging(Bucket=self.upload_bucket_name, Key=file_key,
                                              Tagging={'TagSet': tag_set})
        return s3obj

    @patch('upload.docker_images.checksummer.checksummer.update_event')
    def test_checksummer_checksums(self, mock_update_checksum_event):
        filename = "foo"
        file_contents = "exquisite corpse"
        file_s3_key = f"{self.upload_area_id}/{filename}"
        self._mock_upload_file(filename, contents=file_contents)
        s3_url = f"s3://{self.upload_bucket_name}/{file_s3_key}"

        with EnvironmentSetup(self.environment):
            # from checksummer import Checksummer
            Checksummer([s3_url, self.checksum_id])

        tagging = boto3.client('s3').get_object_tagging(Bucket=self.upload_bucket_name, Key=file_s3_key)
        self.assertEqual(
            sorted(tagging['TagSet'], key=lambda x: x['Key']),
            sorted(FIXTURE_DATA_CHECKSUMS[file_contents]['s3_tagset'], key=lambda x: x['Key'])
        )


if __name__ == '__main__':
    unittest.main()
