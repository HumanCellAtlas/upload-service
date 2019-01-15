import uuid

import boto3

from .. import UploadTestCaseUsingMockAWS
from ... import FIXTURE_DATA_CHECKSUMS

from upload.common.upload_area import UploadArea
from upload.common.dss_checksums import DssChecksums


class TestDssChecksums(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()

        self.upload_area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.upload_area_id)
        self.upload_area.update_or_create()

        self.checksum_id = str(uuid.uuid4())
        self.job_id = str(uuid.uuid4())

        self.s3client = boto3.client('s3')

    def tearDown(self):
        super().tearDown()

    def test_it_acts_like_a_dict(self):
        checksums = DssChecksums(s3_object=None, checksums={'crc32c': 'a', 'sha1': 'b', 'sha256': 'c', 's3_etag': 'd'})
        self.assertEqual(4, len(checksums))
        self.assertEqual('b', checksums['sha1'])
        self.assertIn('sha256', checksums)
        self.assertEqual(['crc32c', 's3_etag', 'sha1', 'sha256'], sorted(checksums.keys()))

    def test_are_present__for_an_object_with_no_checksums__returns_false(self):
        filename = 'file1'
        s3obj = self.mock_upload_file_to_s3(self.upload_area_id, filename, checksums={})

        self.assertFalse(DssChecksums(s3_object=s3obj).are_present())

    def test_are_present__for_an_object_with_partial_checksums__returns_false(self):
        filename = 'file2'
        s3obj = self.mock_upload_file_to_s3(self.upload_area_id, filename, checksums={
            'sha1': '1',
            'sha256': '2'
        })

        self.assertFalse(DssChecksums(s3_object=s3obj).are_present())

    def test_are_present__for_an_object_with_all_checksums__returns_true(self):
        filename = 'file3'
        s3obj = self.mock_upload_file_to_s3(self.upload_area_id, filename, checksums={
            'sha1': '1',
            'sha256': '2',
            's3_etag': '3',
            'crc32c': '4'
        })

        self.assertTrue(DssChecksums(s3_object=s3obj).are_present())

    def test_init_reads_checksums_from_s3_object(self):
        s3obj = self.create_s3_object(object_key="file4")
        tagging = [
            {'Key': 'hca-dss-sha1', 'Value': '1'},
            {'Key': 'hca-dss-sha256', 'Value': '2'},
            {'Key': 'hca-dss-crc32c', 'Value': '3'},
            {'Key': 'hca-dss-s3_etag', 'Value': '4'}
        ]
        self.s3client.put_object_tagging(Bucket=s3obj.bucket_name,
                                         Key=s3obj.key,
                                         Tagging={'TagSet': tagging})

        checksums = DssChecksums(s3_object=s3obj)

        self.assertEqual({'crc32c': '3', 'sha1': '1', 'sha256': '2', 's3_etag': '4'}, checksums)

    def test_compute(self):
        filename = 'bar'
        file_contents = "exquisite corpse"
        s3obj = self.mock_upload_file_to_s3(self.upload_area_id, filename, contents=file_contents)

        self.assertEqual(
            DssChecksums(s3_object=s3obj).compute(),
            FIXTURE_DATA_CHECKSUMS[file_contents]['checksums']
        )

    def test_save_as_tags_on_s3_object(self):
        s3obj = self.create_s3_object(object_key="foo")

        checksums = DssChecksums(s3obj, checksums={'sha1': 'a', 'sha256': 'b', 'crc32c': 'c', 's3_etag': 'd'})
        checksums.save_as_tags_on_s3_object()

        self.assertEqual(
            [
                {'Key': 'hca-dss-sha1', 'Value': 'a'},
                {'Key': 'hca-dss-sha256', 'Value': 'b'},
                {'Key': 'hca-dss-crc32c', 'Value': 'c'},
                {'Key': 'hca-dss-s3_etag', 'Value': 'd'}
            ],
            self.s3client.get_object_tagging(Bucket=self.upload_area.bucket_name, Key=s3obj.key)['TagSet'])
