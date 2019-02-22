import json
import os
import random
import subprocess
import time
import unittest

import boto3
import requests

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
        _start_time = time.time()
        self.api_url = f"https://{os.environ['API_HOST']}/v1"
        self.upload_config = UploadConfig()
        self.auth_headers = {'Api-Key': self.upload_config.api_key}
        self.deployment_stage = os.environ['DEPLOYMENT_STAGE']
        self.upload_area_uuid = "deadbeef-dead-dead-dead-%012d" % random.randint(0, 999999999999)
        self.verbose = True
        _end_time = time.time()
        print(f"Total startup time: {_end_time - _start_time} seconds.")

    def test__upload_small_file__successful(self):
        # Test variables
        _start_time = time.time()
        _small_file = FixtureFile.factory('small_file')

        # Run test
        print(f"\n\nUsing environment {self.deployment_stage} at URL {self.api_url}.\n")
        self._execute_create_upload_area()

        self._execute_upload_file_using_cli(_small_file.path)
        self._verify_file_was_checksummed_inline(_small_file)

        _validation_id = self._execute_validate_file(_small_file)
        self._verify_file_validation_status(_validation_id)  # default parameters checks for success in validation

        self._execute_forget_upload_area()
        self._execute_delete_upload_area()

        _end_time = time.time()
        print(f"Total test_upload__small_file__successful time: {_end_time - _start_time} seconds.")

    def test__upload_large_file__successful(self):
        # Test variables
        _start_time = time.time()
        _large_file = FixtureFile.factory('10241MB_file')

        # Run test
        print(f"\n\nUsing environment {self.deployment_stage} at URL {self.api_url}.\n")
        self._execute_create_upload_area()

        self._execute_upload_file_using_cli(_large_file.url)
        self._verify_file_is_checksummed_via_batch(_large_file)

        self._execute_forget_upload_area()
        self._execute_delete_upload_area()

        _end_time = time.time()
        print(f"Total test__upload_large_file__successful time: {_end_time - _start_time} seconds.")

    def test__upload_invalid_file__validation_result_shows_invalid_state(self):
        # Test variables
        _start_time = time.time()
        _invalid_file = FixtureFile.factory('small_invalid_file')

        # Run test
        print(f"\n\nUsing environment {self.deployment_stage} at URL {self.api_url}.\n")
        self._execute_create_upload_area()

        self._execute_upload_file_using_cli(_invalid_file.path)
        self._verify_file_was_checksummed_inline(_invalid_file)

        _validation_id = self._execute_validate_file(_invalid_file)

        # Verify that the validation result of the file is invalid. This is designated by an exit code of 1 and the
        # presence of an error message saying that file is invalid.
        self._verify_file_validation_status(_validation_id, 1, "invalid")

        self._execute_forget_upload_area()
        self._execute_delete_upload_area()

        _end_time = time.time()
        print(
            f"Total test__upload_invalid_file__validation_result_shows_invalid_state time: {_end_time - _start_time} "
            f"seconds.")

    def _execute_create_upload_area(self):
        response = self._make_request(description="CREATE UPLOAD AREA",
                                      verb='POST',
                                      url=f"{self.api_url}/area/{self.upload_area_uuid}",
                                      headers=self.auth_headers,
                                      expected_status=201)
        data = json.loads(response)
        self.uri = data['uri']
        self.assertEqual('UNLOCKED', self._get_upload_area_record_status())

    def _execute_upload_file_using_cli(self, file_location):
        self._run_cli_command("SELECT UPLOAD AREA", ['hca', 'upload', 'select', self.uri])
        self._run_cli_command("UPLOAD FILE USING CLI", ['hca', 'upload', 'files', file_location])

    def _execute_validate_file(self, test_file):
        response = self._make_request(description="VALIDATE",
                                      verb='PUT',
                                      url=f"{self.api_url}/area/{self.upload_area_uuid}/{test_file.name}/validate",
                                      expected_status=200,
                                      headers=self.auth_headers,
                                      json={"validator_image": "humancellatlas/upload-validator-example:14"})
        validation_id = json.loads(response)['validation_id']

        WaitFor(self._get_validation_record_status, validation_id) \
            .to_return_value('SCHEDULED', timeout_seconds=MINUTE_SEC)

        validation_job_id = self._get_validation_record_job_id(validation_id)

        WaitFor(self._get_batch_job_status, validation_job_id) \
            .to_return_value('SUCCEEDED', timeout_seconds=20 * MINUTE_SEC)

        WaitFor(self._get_validation_record_status, validation_id) \
            .to_return_value('VALIDATED', timeout_seconds=MINUTE_SEC)

        return validation_id

    def _execute_forget_upload_area(self):
        self._run_cli_command("FORGET UPLOAD AREA", ['hca', 'upload', 'forget', self.upload_area_uuid])

    def _execute_delete_upload_area(self):
        self._make_request(description="DELETE UPLOAD AREA",
                           verb='DELETE',
                           url=f"{self.api_url}/area/{self.upload_area_uuid}",
                           headers=self.auth_headers,
                           expected_status=202)
        WaitFor(self._get_upload_area_record_status) \
            .to_return_value('DELETED', timeout_seconds=MINUTE_SEC)

    def _verify_file_was_checksummed_inline(self, test_file):
        """ For files that are smaller than 10G, we expect that the file will be check-summed inline. This means that
        there is no need to schedule a job in batch and no job id is given to the checksum record."""
        print("VERIFYING FILE WAS CHECKSUMMED INLINE...")

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
        self.assertEqual(
            sorted(tagging['TagSet'], key=lambda x: x['Key']),
            test_file.s3_tagset
        )

    def _verify_file_is_checksummed_via_batch(self, test_file):
        """ For files that are 10G or larger, we expect that the file will check-summed via batch. This means that it
        first will need to be scheduled and the checksum record will be given a respective job id."""
        print("VERIFYING FILE WAS CHECKSUMMED VIA BATCH...")

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
        self.assertEqual(test_file.checksums, file_record.checksums)

        # Check S3 object has checksum tags
        tagging = boto3.client('s3').get_object_tagging(Bucket=self.upload_config.bucket_name,
                                                        Key=f"{self.upload_area_uuid}/{test_file.name}")
        self.assertEqual(
            sorted(tagging['TagSet'], key=lambda x: x['Key']),
            test_file.s3_tagset
        )

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

    def _make_request(self, description, verb, url, expected_status=None, **options):
        print(description + ": ")
        print(f"{verb.upper()} {url}")

        method = getattr(requests, verb.lower())
        response = method(url, **options)

        print(f"-> {response.status_code}")
        if expected_status:
            self.assertEqual(expected_status, response.status_code)

        if response.content:
            print(response.content.decode('utf8'))

        return response.content

    def _run_cli_command(self, description, command, expected_returncode=0):
        print("\n" + description + ": ")
        print(' '.join(command))
        completed_process = subprocess.run(command, stdout=None, stderr=None)
        self.assertEqual(expected_returncode, completed_process.returncode)
