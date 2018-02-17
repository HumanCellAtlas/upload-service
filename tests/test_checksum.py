import unittest
import uuid

import boto3
from moto import mock_s3

from . import EnvironmentSetup

with EnvironmentSetup({'DCP_EVENTS_TOPIC': 'foo'}):  # noqa
    from upload import UploadArea

from upload.checksum import UploadedFileChecksummer


class TestUploadedFileChecksummer(unittest.TestCase):

    def setUp(self):
        # Setup mock AWS
        self.s3_mock = mock_s3()
        self.s3_mock.start()

        # Setup upload bucket
        self.deployment_stage = 'test'
        self.upload_bucket_name = f'bogobucket'
        self.upload_bucket = boto3.resource('s3').Bucket(self.upload_bucket_name)
        self.upload_bucket.create()
        self.environment = {
            'BUCKET_NAME': self.upload_bucket_name,
            'DEPLOYMENT_STAGE': self.deployment_stage
        }
        self.upload_area_id = uuid.uuid4()
        with EnvironmentSetup(self.environment):
            self.upload_area = UploadArea(self.upload_area_id)

    def tearDown(self):
        self.s3_mock.stop()

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

    def test_has_checksums_returns_false_for_file_with_no_checksums(self):
        filename = 'bar'
        self._mock_upload_file(filename=filename, checksums=None)
        with EnvironmentSetup(self.environment):
            uf = self.upload_area.uploaded_file(filename)

            self.assertFalse(UploadedFileChecksummer(uploaded_file=uf).has_checksums())

    def test_has_checksums_returns_false_for_file_with_some_checksums(self):
        filename = 'bar'
        self._mock_upload_file(filename=filename, checksums={
            'sha1': '1',
            'sha256': '2'
        })
        with EnvironmentSetup(self.environment):
            uf = self.upload_area.uploaded_file(filename)

            self.assertFalse(UploadedFileChecksummer(uploaded_file=uf).has_checksums())

    def test_has_checksums_returns_true_for_file_with_all_checksums(self):
        filename = 'bar'
        self._mock_upload_file(filename=filename, checksums={
            'sha1': '1',
            'sha256': '2',
            's3_etag': '3',
            'crc32c': '4'
        })
        uf = self.upload_area.uploaded_file(filename)

        self.assertTrue(UploadedFileChecksummer(uploaded_file=uf).has_checksums())

    def test_checksum(self):
        filename = 'bar'
        self._mock_upload_file(filename=filename, contents="exquisite corpse")
        uf = self.upload_area.uploaded_file(filename)

        self.assertEqual(UploadedFileChecksummer(uploaded_file=uf).checksum(), {
            's3_etag': '18f17fbfdd21cf869d664731e10d4ffd',
            'sha1': 'b1b101e21cf9cf8a4729da44d7818f935eec0ce8',
            'sha256': '29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70',
            'crc32c': 'FE9ADA52'
        })
