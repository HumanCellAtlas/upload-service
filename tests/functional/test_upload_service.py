import json
import os
import random
import subprocess
import unittest

import boto3
import requests

from .waitfor import WaitFor
from .. import FixtureFile

from upload.common.upload_config import UploadConfig
from upload.common.database_orm import DbUploadArea, DbFile, DbChecksum, DbValidation, DBSessionMaker

MINUTE_SEC = 60


class TestUploadService(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch = boto3.client('batch')
        self.uri = None
        self.db_session_maker = DBSessionMaker()

    def setUp(self):
        self.upload_config = UploadConfig()
        self.deployment_stage = os.environ['DEPLOYMENT_STAGE']
        self.auth_headers = {'Api-Key': self.upload_config.api_key}
        self.api_url = f"https://{os.environ['API_HOST']}/v1"
        self.verbose = True

    def testIt(self):
        print(f"\n\nUsing environment {self.deployment_stage} at URL {self.api_url}.\n")

        self.upload_area_uuid = "deadbeef-dead-dead-dead-%012d" % random.randint(0, 999999999999)
        self._create_upload_area()

        small_file = FixtureFile.factory('small_file')

        self._upload_file_using_cli(small_file.path)
        self._verify_file_was_checksummed_inline(small_file)

        # large_file = FixtureFile.factory('10241MB_file')
        # self._upload_file_using_cli(large_file.url)
        # self._verify_file_is_checksummed_via_batch(large_file)

        self._validate_file(small_file)

        self._forget_upload_area()
        self._delete_upload_area()

    def _create_upload_area(self):
        response = self._make_request(description="CREATE UPLOAD AREA",
                                      verb='POST',
                                      url=f"{self.api_url}/area/{self.upload_area_uuid}",
                                      headers=self.auth_headers,
                                      expected_status=201)
        data = json.loads(response)
        self.uri = data['uri']
        self.assertEqual('UNLOCKED', self._upload_area_record_status())

    def _upload_file_using_cli(self, file_location):
        self._run("SELECT UPLOAD AREA", ['hca', 'upload', 'select', self.uri])
        self._run("UPLOAD FILE USING CLI", ['hca', 'upload', 'files', file_location])

    def _verify_file_was_checksummed_inline(self, test_file):
        print("VERIFY FILE WAS CHECKSUMMED INLINE...")
        WaitFor(self._checksum_record_status, test_file.name)\
            .to_return_value('CHECKSUMMED', timeout_seconds=300)

        # Inline checksums get no job_id
        checksum_record = self._checksum_record(test_file.name)
        self.assertEqual(None, checksum_record.job_id)

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
        WaitFor(self._checksum_record_status, test_file.name)\
            .to_return_value('SCHEDULED', timeout_seconds=30)

        csum_record = self._checksum_record(test_file.name)
        WaitFor(self._batch_job_status, csum_record.job_id)\
            .to_return_value('SUCCEEDED', timeout_seconds=20 * MINUTE_SEC)

        checksum_record = self._checksum_record(test_file.name)
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

    def _validate_file(self, test_file):
        response = self._make_request(description="VALIDATE",
                                      verb='PUT',
                                      url=f"{self.api_url}/area/{self.upload_area_uuid}/{test_file.name}/validate",
                                      expected_status=200,
                                      headers=self.auth_headers,
                                      json={"validator_image": "humancellatlas/upload-validator-example"})
        validation_id = json.loads(response)['validation_id']

        WaitFor(self._validation_record_status, validation_id)\
            .to_return_value('SCHEDULED', timeout_seconds=MINUTE_SEC)

        validation_job_id = self._validation_record_job_id(validation_id)

        WaitFor(self._batch_job_status, validation_job_id)\
            .to_return_value('SUCCEEDED', timeout_seconds=20 * MINUTE_SEC)

        WaitFor(self._validation_record_status, validation_id)\
            .to_return_value('VALIDATED', timeout_seconds=MINUTE_SEC)

        # TODO: check validation results

    def _forget_upload_area(self):
        self._run("FORGET UPLOAD AREA", ['hca', 'upload', 'forget', self.upload_area_uuid])

    def _delete_upload_area(self):
        self._make_request(description="DELETE UPLOAD AREA",
                           verb='DELETE',
                           url=f"{self.api_url}/area/{self.upload_area_uuid}",
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
        return db.query(DbUploadArea).filter(DbUploadArea.uuid == self.upload_area_uuid).one_or_none()

    def _checksum_record(self, filename):
        db = self.db_session_maker.session()
        s3_key = f"{self.upload_area_uuid}/{filename}"
        file_record = db.query(DbFile).filter(DbFile.s3_key == s3_key).one_or_none()
        if file_record is None:
            return None
        checksum_record = db.query(DbChecksum).filter(DbChecksum.file_id == file_record.id).one_or_none()
        return checksum_record

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
