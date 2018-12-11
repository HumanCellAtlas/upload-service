import uuid

from .. import UploadTestCaseUsingMockAWS
from ... import FIXTURE_DATA_CHECKSUMS

from upload.common.upload_area import UploadArea
from upload.common.checksum import UploadedFileChecksummer


class TestUploadedFileChecksummer(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()

        self.upload_area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.upload_area_id)
        self.upload_area.update_or_create()

        self.checksum_id = str(uuid.uuid4())
        self.job_id = str(uuid.uuid4())

    def tearDown(self):
        super().tearDown()

    def test_has_checksums_returns_false_for_file_with_no_checksums(self):
        filename = 'bar'
        self.mock_upload_file(self.upload_area_id, filename, checksums={})
        uf = self.upload_area.uploaded_file(filename)

        self.assertFalse(UploadedFileChecksummer(uploaded_file=uf).has_checksums())

    def test_has_checksums_returns_false_for_file_with_some_checksums(self):
        filename = 'bar'
        self.mock_upload_file(self.upload_area_id, filename, checksums={
            'sha1': '1',
            'sha256': '2'
        })
        uf = self.upload_area.uploaded_file(filename)

        self.assertFalse(UploadedFileChecksummer(uploaded_file=uf).has_checksums())

    def test_has_checksums_returns_true_for_file_with_all_checksums(self):
        filename = 'bar'
        self.mock_upload_file(self.upload_area_id, filename, checksums={
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
        self.mock_upload_file(self.upload_area_id, filename, contents=file_contents)
        uf = self.upload_area.uploaded_file(filename)

        self.assertEqual(
            UploadedFileChecksummer(uploaded_file=uf).checksum(),
            FIXTURE_DATA_CHECKSUMS[file_contents]['checksums']
        )
