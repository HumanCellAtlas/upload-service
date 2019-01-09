import uuid

import boto3

from .. import UploadTestCaseUsingMockAWS

from upload.common.upload_area import UploadArea
from upload.common.checksum_tagger import ChecksumTagger


class TestChecksumTagger(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        self.upload_area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.upload_area_id)
        self.upload_area.update_or_create()
        self.s3client = boto3.client('s3')

    def test_apply_checksum_tags_to_s3_object(self):
        s3obj = self.create_s3_object(object_key="foo")
        checksums = {'sha1': 'a', 'sha256': 'b', 'crc32c': 'c', 's3_etag': 'd'}

        ChecksumTagger(s3obj).save_checksums_as_tags_on_s3_object(checksums)

        self.assertEqual(
            [
                {'Key': 'hca-dss-sha1', 'Value': 'a'},
                {'Key': 'hca-dss-sha256', 'Value': 'b'},
                {'Key': 'hca-dss-crc32c', 'Value': 'c'},
                {'Key': 'hca-dss-s3_etag', 'Value': 'd'}
            ],
            self.s3client.get_object_tagging(Bucket=self.upload_area.bucket_name, Key=s3obj.key)['TagSet'])

    def test_read_checksums(self):
        filename = "file1"
        s3obj = self.create_s3_object(object_key=f"{self.upload_area.uuid}/{filename}")
        tagging = [
            {'Key': 'hca-dss-sha1', 'Value': '1'},
            {'Key': 'hca-dss-sha256', 'Value': '2'},
            {'Key': 'hca-dss-crc32c', 'Value': '3'},
            {'Key': 'hca-dss-s3_etag', 'Value': '4'}
        ]
        self.s3client.put_object_tagging(Bucket=s3obj.bucket_name,
                                         Key=s3obj.key,
                                         Tagging={'TagSet': tagging})

        checksums = ChecksumTagger(s3obj).read_checksums()

        self.assertEqual({'sha1': '1', 'sha256': '2', 'crc32c': '3', 's3_etag': '4'}, checksums)
