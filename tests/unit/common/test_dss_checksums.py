import uuid

import boto3

from upload.common.dss_checksums import DssChecksums, __name__ as logger_name
from upload.common.exceptions import UploadException
from upload.common.logging import get_logger
from upload.common.upload_area import UploadArea
from .. import UploadTestCaseUsingMockAWS
from ... import FixtureFile


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
        _checksums_input = {'crc32c': 'a', 'sha1': 'b', 'sha256': 'c', 's3_etag': 'd'}
        _dss_checksums = DssChecksums(s3_object=None, checksums=_checksums_input)

        self.assertEquals(_dss_checksums, _checksums_input)

    def test__upload_file_with_no_checksums__insufficientChecksums(self):
        _filename = 'file'
        _checksums = {}

        _s3obj = self.mock_upload_file_to_s3(self.upload_area_id, _filename, checksums=_checksums)

        self.assertFalse(DssChecksums(s3_object=_s3obj).are_present())

    def test__upload_file_with_partial_checksums__insufficientChecksums(self):
        _filename = 'file'
        _checksums = {'sha1': '1', 'sha256': '2'}

        _s3obj = self.mock_upload_file_to_s3(self.upload_area_id, _filename, checksums=_checksums)

        self.assertFalse(DssChecksums(s3_object=_s3obj).are_present())

    def test__upload_file_with_full_checksums__succeeds(self):
        _filename = 'file'
        _checksums = {'sha1': '1', 'sha256': '2', 's3_etag': '3', 'crc32c': '4'}

        _s3obj = self.mock_upload_file_to_s3(self.upload_area_id, _filename, checksums=_checksums)

        self.assertTrue(DssChecksums(s3_object=_s3obj).are_present())

    def test__upload_file_with_checksums__checksums_match_input(self):
        _filename = 'file'
        _checksums = {'crc32c': '3', 'sha1': '1', 'sha256': '2', 's3_etag': '4'}
        _tagging = [{'Key': 'hca-dss-' + _hash_function, 'Value': _value} for _hash_function, _value in
                    _checksums.items()]
        _s3obj = self.create_s3_object(object_key=_filename, checksum_value={'crc32c': '3'})

        self.s3client.put_object_tagging(Bucket=_s3obj.bucket_name,
                                         Key=_s3obj.key,
                                         Tagging={'TagSet': _tagging})
        _dss_checksums = DssChecksums(s3_object=_s3obj)

        self.assertEqual(_checksums, _dss_checksums)

    def test__upload_file_with_missing_clientside_checksums__fails(self):
        _filename = 'file'
        _checksums = {'crc32c': '3', 'sha1': '1', 'sha256': '2', 's3_etag': '4'}

        _s3obj = self.create_s3_object(object_key=_filename, checksum_value={})
        _checksums = DssChecksums(_s3obj, checksums=_checksums)

        with self.assertLogs(logger=get_logger(logger_name)) as _context_manager:
            _checksums.save_as_tags_on_s3_object()
            self.assertIn("crc32c was not found in the metadata of the file", str(_context_manager.output))

    def test__upload_file_with_mismatched_clientside_checksum_fails(self):
        _filename = 'file'
        _checksums = {'crc32c': '3', 'sha1': '1', 'sha256': '2', 's3_etag': '4'}

        _s3obj = self.create_s3_object(object_key=_filename, checksum_value={'crc32c': 'I do not match!'})
        _checksums = DssChecksums(_s3obj, checksums=_checksums)

        with self.assertRaises(UploadException) as _upload_exception:
            _checksums.save_as_tags_on_s3_object()

        self.assertIn("checksum values stored as metadata did not match", _upload_exception.exception.detail)

    def test__compute_checksums__succeeds(self):
        _test_file = FixtureFile.factory("foo")

        _s3obj = self.mock_upload_file_to_s3(self.upload_area_id, _test_file.name, contents=_test_file.contents)

        self.assertEqual(DssChecksums(s3_object=_s3obj).compute(), _test_file.checksums)

    def test__save_as_tags_on_s3_object__succeeds(self):
        _filename = "foo"
        _checksums = {'sha1': 'a', 'sha256': 'b', 'crc32c': 'c', 's3_etag': 'd'}
        _clientside_checksums = {'crc32c': 'c'}
        _s3obj = self.create_s3_object(object_key=_filename, checksum_value=_clientside_checksums)

        checksums = DssChecksums(_s3obj, checksums=_checksums)
        checksums.save_as_tags_on_s3_object()

        self.assertEqual(
            [{'Key': 'hca-dss-' + _hash_function, 'Value': _value} for _hash_function, _value in _checksums.items()],
            self.s3client.get_object_tagging(Bucket=self.upload_area.bucket_name, Key=_s3obj.key)['TagSet'])
