from upload.common.client_side_checksum_handler import ClientSideChecksumHandler, CHECKSUM_NAMES, \
    __name__ as logger_name
from upload.common.logging import get_logger
from .. import UploadTestCaseUsingMockAWS
from ... import FixtureFile


class TestClientSideChecksumHandler(UploadTestCaseUsingMockAWS):
    """ This class contains unit tests for the ClientSideChecksumHandler class. """

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test__get_tag_given_data__returns_crc32c_tag(self):
        _test_file = FixtureFile.factory("foo")

        _checksum_handler = ClientSideChecksumHandler(data=_test_file.contents)
        _checksums = _checksum_handler.get_checksum_metadata_tag()

        [self.assertEquals(_checksums[_hash_function], _test_file.checksums[_hash_function]) for _hash_function in
         CHECKSUM_NAMES]

    def test__get_tag_given_filename__returns_crc32c_tag(self):
        _test_file = FixtureFile.factory("small_file")

        _checksum_handler = ClientSideChecksumHandler(filename=FixtureFile.fixture_file_path(_test_file.name))
        _checksums = _checksum_handler.get_checksum_metadata_tag()

        [self.assertEquals(_checksums[_hash_function], _test_file.checksums[_hash_function]) for _hash_function in
         CHECKSUM_NAMES]

    def test__get_tag_given_s3_file__returns_warning(self):
        _test_file = FixtureFile.factory("10241MB_file")

        with self.assertLogs(logger=get_logger(logger_name)) as context_manager:
            _checksum_handler = ClientSideChecksumHandler(filename=_test_file.url)
            _checksums = _checksum_handler.get_checksum_metadata_tag()

            self.assertIn("Did not perform client-side checksumming for file in S3", str(context_manager.output))
            self.assertIn("No checksums have been computed", str(context_manager.output))
            self.assertEquals(_checksums, {})

    def test__get_tag_given_no_data_nor_filename__returns_warning(self):
        with self.assertLogs(logger=get_logger(logger_name)) as context_manager:
            _checksum_handler = ClientSideChecksumHandler()
            _checksums = _checksum_handler.get_checksum_metadata_tag()

            self.assertIn("no data was provided", str(context_manager.output))
            self.assertIn("No checksums have been computed", str(context_manager.output))
            self.assertEquals(_checksums, {})

    def test__get_tag_given_both_data_and_filename__returns_warning(self):
        _test_file = FixtureFile.factory("small_file")

        with self.assertLogs(logger=get_logger(logger_name)) as context_manager:
            _checksum_handler = ClientSideChecksumHandler(data=_test_file.contents,
                                                          filename=FixtureFile.fixture_file_path(_test_file.name))
            _checksums = _checksum_handler.get_checksum_metadata_tag()

            self.assertIn("both a file and raw data was provided", str(context_manager.output))
            self.assertIn("No checksums have been computed", str(context_manager.output))
            self.assertEquals(_checksums, {})
