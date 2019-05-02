import json
import os
import random
import subprocess
import time
import unittest

import boto3
import requests

from hca.upload import UploadService
from upload.common.database_orm import DbUploadArea, DbFile, DbChecksum, DbValidation, DBSessionMaker
from upload.common.upload_config import UploadConfig
from .waitfor import WaitFor
from .. import FixtureFile

MINUTE_SEC = 60


class TestUploadService(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch = boto3.client('batch')
        self.uri = None
        self.db_session_maker = DBSessionMaker()

    def setUp(self):
        self.test_start_time = time.time()
        self.upload_config = UploadConfig()
        self.upload_client = UploadService(
            deployment_stage=os.environ['DEPLOYMENT_STAGE'],
            api_token=self.upload_config.api_key
        )
        self.upload_area_uuid = "deadbeef-dead-dead-dead-%012d" % random.randint(0, 999999999999)
        print("")
        self._execute_create_upload_area()
        print("\tstartup time: %0.02f seconds." % (time.time() - self.test_start_time))

    def tearDown(self):
        test_end_time = time.time()
        print("\t%s took %0.02f seconds." % (self._testMethodName, test_end_time - self.test_start_time))
        self._execute_delete_upload_area()
        print("\tteardown time: %0.02f seconds." % (time.time() - test_end_time))

        # All tests are formatted into 2-3 sections separated by blank lines:
        #
        #   Setup preconditions (optional)
        #
        #   Do the thing we are testing
        #
        #   Test the thing was done

    def test_store_file_using_api(self):
        metadata_file = FixtureFile.factory('metadata_file.json')

        self.upload_area.store_file(filename=metadata_file.name,
                                    file_content=metadata_file.contents,
                                    content_type='application/json; dcp-type=metadata')

        self._verify_file_was_checksummed_inline(metadata_file)  # Implicitly tests file was created.

    def test_store_file_using_cli(self):
        """ Tests storing of a file directly in S3, then notification of Upload via REST API """
        small_file = FixtureFile.factory('small_file')

        self._execute_upload_file_using_cli(small_file.path)

        self._verify_file_was_checksummed_inline(small_file)  # Implicitly tests file was created.

    def test_store_file_using_cli__with_large_file__triggers_batch_checksumming(self):
        large_file = FixtureFile.factory('10241MB_file')

        self._execute_upload_file_using_cli(large_file.url)

        self._verify_file_is_checksummed_via_batch(large_file)

    def test_validate_file__with_valid_file__reports_validation_results(self):
        small_file = FixtureFile.factory('small_file')
        self.upload_area.store_file(filename=small_file.name,
                                    file_content=small_file.contents,
                                    content_type='application/json; dcp-type=data')

        response = self.upload_area.validate_files(file_list=[small_file.name],
                                                   validator_image="humancellatlas/upload-validator-example:14")

        validation_id = response['validation_id']
        self._wait_for_validation_to_complete(validation_id)
        self._verify_file_validation_status(validation_id)  # default parameters checks for success in validation

    def test__upload_invalid_file__validation_result_shows_invalid_state(self):
        invalid_file = FixtureFile.factory('small_invalid_file')
        self.upload_area.store_file(filename=invalid_file.name,
                                    file_content=invalid_file.contents,
                                    content_type='application/json; dcp-type=data')

        response = self.upload_area.validate_files(file_list=[invalid_file.name],
                                                   validator_image="humancellatlas/upload-validator-example:14")

        validation_id = response['validation_id']
        self._wait_for_validation_to_complete(validation_id)
        # Verify that the validation result of the file is invalid. This is designated by an exit code of 1 and the
        # presence of an error message saying that file is invalid.
        self._verify_file_validation_status(validation_id, expected_exit_code=1, expected_error_msg="invalid")

    def _execute_create_upload_area(self):
        self.upload_area = self.upload_client.create_area(self.upload_area_uuid)
        self.assertEqual('UNLOCKED', self._get_upload_area_record_status())
        print(f"\tCreated upload area {self.upload_area_uuid}")

    def _execute_upload_file_using_cli(self, file_location):
        self._run_cli_command('hca', 'upload', 'select', str(self.upload_area.uri))
        self._run_cli_command('hca', 'upload', 'files', file_location)
        self._run_cli_command('hca', 'upload', 'forget', self.upload_area.uuid)

    def _wait_for_validation_to_complete(self, validation_id):
        WaitFor(self._get_validation_record_status, validation_id) \
            .to_return_value('SCHEDULED', timeout_seconds=MINUTE_SEC)

        validation_job_id = self._get_validation_record_job_id(validation_id)

        WaitFor(self._get_batch_job_status, validation_job_id) \
            .to_return_value('SUCCEEDED', timeout_seconds=20 * MINUTE_SEC)

        WaitFor(self._get_validation_record_status, validation_id) \
            .to_return_value('VALIDATED', timeout_seconds=MINUTE_SEC)

    def _execute_delete_upload_area(self):
        print(f"\tDeleting upload area {self.upload_area.uuid}")
        self.upload_area.delete()
        WaitFor(self._get_upload_area_record_status) \
            .to_return_value('DELETED', timeout_seconds=MINUTE_SEC)

    def _verify_file_was_checksummed_inline(self, test_file):
        """ For files that are smaller than 10G, we expect that the file will be check-summed inline. This means that
        there is no need to schedule a job in batch and no job id is given to the checksum record."""
        print("\tVerifying file was checksummed inline...")

        WaitFor(self._get_checksum_record_status, test_file.name) \
            .to_return_value('CHECKSUMMED', timeout_seconds=300)

        # Verify that the inline checksum was not assigned a job id.
        checksum_record = self._get_checksum_record(test_file.name)
        self.assertIsNone(checksum_record.job_id)

        # Check file record now contains checksums
        db = self.db_session_maker.session()
        file_record = db.query(DbFile).get(checksum_record.file_id)
        self.assertEqual(test_file.checksums, file_record.checksums)

        # Check S3 object has checksum tags
        tagging = boto3.client('s3').get_object_tagging(Bucket=self.upload_config.bucket_name,
                                                        Key=f"{self.upload_area_uuid}/{test_file.name}")

        _actual_checksums = self._get_dict_representation_of_tagset_case_insensitive(tagging['TagSet'])
        _expected_checksums = self._get_dict_representation_of_tagset_case_insensitive(test_file.s3_tagset)
        self.assertDictEqual(_actual_checksums, _expected_checksums)

    def _verify_file_is_checksummed_via_batch(self, test_file):
        """ For files that are 10G or larger, we expect that the file will check-summed via batch. This means that it
        first will need to be scheduled and the checksum record will be given a respective job id."""
        print("\tVerifying file was checksummed via batch...")

        WaitFor(self._get_checksum_record_status, test_file.name) \
            .to_return_value('SCHEDULED', timeout_seconds=30)
        checksum_record = self._get_checksum_record(test_file.name)
        WaitFor(self._get_batch_job_status, checksum_record.job_id) \
            .to_return_value('SUCCEEDED', timeout_seconds=20 * MINUTE_SEC)
        checksum_record = self._get_checksum_record(test_file.name)

        self.assertEqual('CHECKSUMMED', checksum_record.status)

        # Check file record now contains checksums
        db = self.db_session_maker.session()
        file_record = db.query(DbFile).get(checksum_record.file_id)
        [self.assertEquals(test_file.checksums[_checksum_function].lower(),
                           file_record.checksums[_checksum_function].lower())
         for _checksum_function in set(list(test_file.checksums.keys()) + list(file_record.checksums.keys()))]

        # Check S3 object has checksum tags
        tagging = boto3.client('s3').get_object_tagging(Bucket=self.upload_config.bucket_name,
                                                        Key=f"{self.upload_area_uuid}/{test_file.name}")

        _actual_checksums = self._get_dict_representation_of_tagset_case_insensitive(tagging['TagSet'])
        _expected_checksums = self._get_dict_representation_of_tagset_case_insensitive(test_file.s3_tagset)
        self.assertDictEqual(_actual_checksums, _expected_checksums)

    def _verify_file_validation_status(self, validation_id, expected_exit_code=0, expected_error_msg=''):
        # Get the validation status of the file
        _validation_results = self._get_validation_record(validation_id).results
        _actual_exit_code = _validation_results['exit_code']
        _actual_error_msg = _validation_results['stdout']

        self.assertEqual(expected_exit_code, _actual_exit_code)
        self.assertIn(expected_error_msg, _actual_error_msg)

    def _get_upload_area_record_status(self):
        record = self._get_upload_area_record()
        return record.status if record else None

    def _get_checksum_record_status(self, filename):
        record = self._get_checksum_record(filename)
        return record.status if record else None

    def _get_validation_record_job_id(self, validation_id):
        record = self._get_validation_record(validation_id)
        return record.job_id if record else None

    def _get_validation_record_status(self, validation_id):
        record = self._get_validation_record(validation_id)
        return record.status if record else None

    def _get_upload_area_record(self):
        db = self.db_session_maker.session()
        return db.query(DbUploadArea).filter(DbUploadArea.uuid == self.upload_area_uuid).one_or_none()

    def _get_checksum_record(self, filename):
        db = self.db_session_maker.session()
        s3_key = f"{self.upload_area_uuid}/{filename}"
        file_record = db.query(DbFile).filter(DbFile.s3_key == s3_key).one_or_none()
        if file_record is None:
            return None
        checksum_record = db.query(DbChecksum).filter(DbChecksum.file_id == file_record.id).one_or_none()
        return checksum_record

    def _get_validation_record(self, validation_id):
        db = self.db_session_maker.session()
        return db.query(DbValidation).filter(DbValidation.id == validation_id).one_or_none()

    def _get_batch_job_status(self, job_id):
        response = self.batch.describe_jobs(jobs=[job_id])
        self.assertEqual(1, len(response['jobs']))
        return response['jobs'][0]['status']

    def _run_cli_command(self, *command, expected_returncode=0):
        print("\t" + ' '.join(command))
        completed_process = subprocess.run(command, stdout=None, stderr=None)
        self.assertEqual(expected_returncode, completed_process.returncode)

    def _get_dict_representation_of_tagset_case_insensitive(self, tagset):
        _tagset_dict = {}
        for _item in tagset:
            _tagset_dict[_item['Key'].lower()] = _item['Value'].lower()
        return _tagset_dict
