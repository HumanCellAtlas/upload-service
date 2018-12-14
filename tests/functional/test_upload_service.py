import json
import os
import random
import subprocess
import unittest

import boto3
import requests

from .waitfor import WaitFor
from .. import fixture_file_path, FIXTURE_DATA_CHECKSUMS

from upload.common.upload_config import UploadConfig
from upload.common.database_orm import DbUploadArea, DbChecksum, DbValidation, DBSessionMaker

MINUTE_SEC = 60


class TestUploadService(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch = boto3.client('batch')
        self.uri = None
        self.db_session_maker = DBSessionMaker()

    def setUp(self):
        self.deployment_stage = os.environ['DEPLOYMENT_STAGE']
        self.auth_headers = {'Api-Key': UploadConfig().api_key}
        self.api_url = f"https://{os.environ['API_HOST']}/v1"
        self.verbose = True

    def testIt(self):
        print(f"\n\nUsing environment {self.deployment_stage} at URL {self.api_url}.\n")

        self.upload_area_id = "deadbeef-dead-dead-dead-%012d" % random.randint(0, 999999999999)
        self._create_upload_area()

        small_file_name = 'small_file'
        small_file_path = fixture_file_path(small_file_name)
        self._upload_file_using_cli(small_file_path)
        self._verify_file_was_checksummed_inline(small_file_name)

        large_file_name = '10241MB_file'
        self._copy_file_directly_to_upload_area(large_file_name)
        self._verify_file_is_checksummed_via_batch(large_file_name)
        self._validate_file(small_file_name)

        self._forget_upload_area()
        self._delete_upload_area()

    def _create_upload_area(self):
        response = self._make_request(description="CREATE UPLOAD AREA",
                                      verb='POST',
                                      url=f"{self.api_url}/area/{self.upload_area_id}",
                                      headers=self.auth_headers,
                                      expected_status=201)
        data = json.loads(response)
        self.uri = data['uri']
        self.assertEqual('UNLOCKED', self._upload_area_record_status())

    def _upload_file_using_cli(self, file_path):
        self._run("SELECT UPLOAD AREA", ['hca', 'upload', 'select', self.uri])
        self._run("UPLOAD FILE USING CLI", ['hca', 'upload', 'files', file_path])

    def _copy_file_directly_to_upload_area(self, filename):
        source_url = f"s3://org-humancellatlas-dcp-test-data/upload_service/{filename}"
        target_url = self.uri + filename
        self._run("COPY S3 FILE TO UPLOAD AREA", ['aws', 's3', 'cp', source_url, target_url])

    def _verify_file_was_checksummed_inline(self, filename):
        print("VERIFY FILE WAS CHECKSUMMED INLINE...")
        WaitFor(self._checksum_record_status, filename)\
            .to_return_value('CHECKSUMMED', timeout_seconds=300)

        # Inline checksums get no job_id
        checksum_record = self._checksum_record(filename)
        self.assertEqual(None, checksum_record.job_id)
        self.assertEqual(FIXTURE_DATA_CHECKSUMS['small_file']['checksums'], checksum_record.checksums)

    def _verify_file_is_checksummed_via_batch(self, filename):
        WaitFor(self._checksum_record_status, filename)\
            .to_return_value('SCHEDULED', timeout_seconds=30)

        csum_record = self._checksum_record(filename)
        WaitFor(self._batch_job_status, csum_record.job_id)\
            .to_return_value('SUCCEEDED', timeout_seconds=20 * MINUTE_SEC)

        checksum_record = self._checksum_record(filename)
        self.assertEqual('CHECKSUMMED', checksum_record.status)
        self.assertEqual(FIXTURE_DATA_CHECKSUMS[filename]['checksums'], checksum_record.checksums)

    def _validate_file(self, filename):
        response = self._make_request(description="VALIDATE",
                                      verb='PUT',
                                      url=f"{self.api_url}/area/{self.upload_area_id}/{filename}/validate",
                                      expected_status=200,
                                      headers=self.auth_headers,
                                      json={"validator_image": "humancellatlas/upload-validator-example"})
        validation_id = json.loads(response)['validation_id']

        validation_job_id = self._validation_record_job_id(validation_id)

        WaitFor(self._batch_job_status, validation_job_id)\
            .to_return_value('SUCCEEDED', timeout_seconds=20 * MINUTE_SEC)

        WaitFor(self._validation_record_status, validation_id)\
            .to_return_value('VALIDATED', timeout_seconds=MINUTE_SEC)

        # TODO: check validation results

    def _forget_upload_area(self):
        self._run("FORGET UPLOAD AREA", ['hca', 'upload', 'forget', self.upload_area_id])

    def _delete_upload_area(self):
        self._make_request(description="DELETE UPLOAD AREA",
                           verb='DELETE',
                           url=f"{self.api_url}/area/{self.upload_area_id}",
                           headers=self.auth_headers,
                           expected_status=202)
        WaitFor(self._upload_area_record_status)\
            .to_return_value('DELETED', timeout_seconds=MINUTE_SEC)

    def _upload_area_record_status(self):
        record = self._upload_area_record()
        return record.status if record else None

    def _checksum_record_status(self, filename):
        record = self._checksum_record(filename)
        return record.status if record else None

    def _validation_record_job_id(self, validation_id):
        record = self._validation_record(validation_id)
        return record.job_id if record else None

    def _validation_record_status(self, validation_id):
        record = self._validation_record(validation_id)
        return record.status if record else None

    def _upload_area_record(self):
        db = self.db_session_maker.session()
        return db.query(DbUploadArea).filter(DbUploadArea.id == self.upload_area_id).one_or_none()

    def _checksum_record(self, filename):
        db = self.db_session_maker.session()
        file_id = f"{self.upload_area_id}/{filename}"
        record = db.query(DbChecksum).filter(DbChecksum.file_id == file_id).one_or_none()
        return record

    def _validation_record(self, validation_id):
        db = self.db_session_maker.session()
        return db.query(DbValidation).filter(DbValidation.id == validation_id).one_or_none()

    def _batch_job_status(self, job_id):
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

    def _run(self, description, command, expected_returncode=0):
        print("\n" + description + ": ")
        print(' '.join(command))
        completed_process = subprocess.run(command, stdout=None, stderr=None)
        self.assertEqual(expected_returncode, completed_process.returncode)
