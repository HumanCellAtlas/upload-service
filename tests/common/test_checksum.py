import unittest
import uuid

import boto3
from moto import mock_s3

from .. import EnvironmentSetup, FIXTURE_DATA_CHECKSUMS

from upload.common.upload_area import UploadArea
from upload.common.checksum import UploadedFileChecksummer


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
            'DEPLOYMENT_STAGE': self.deployment_stage,
            'DCP_EVENTS_TOPIC': 'bogotopic'
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
        file_contents = "exquisite corpse"
        self._mock_upload_file(filename=filename, contents=file_contents)
        uf = self.upload_area.uploaded_file(filename)

        self.assertEqual(
            UploadedFileChecksummer(uploaded_file=uf).checksum(),
            FIXTURE_DATA_CHECKSUMS[file_contents]['checksums']
        )
