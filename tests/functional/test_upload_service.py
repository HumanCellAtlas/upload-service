import base64
import json
import os
import random
import subprocess
import unittest

import boto3
import requests

from .waitfor import WaitFor

from upload.common.database_orm import DbUploadArea, DbChecksum, DbValidation, db_session_maker

MINUTE_SEC = 60


class UploadAreaURN:

    def __init__(self, urn):
        self.urn = urn
        urnbits = urn.split(':')
        assert urnbits[0:3] == ['dcp', 'upl', 'aws'], "URN does not start with 'dcp:upl:aws': %s" % (urn,)
        if len(urnbits) == 5:  # production URN dcp:upl:aws:uuid:creds
            self.deployment_stage = 'prod'
            self.uuid = urnbits[3]
            self.encoded_credentials = urnbits[4]
        elif len(urnbits) == 6:  # non-production URN dcp:upl:aws:stage:uuid:creds
            self.deployment_stage = urnbits[3]
            self.uuid = urnbits[4]
            self.encoded_credentials = urnbits[5]
        else:
            raise RuntimeError("Bad URN: %s" % (urn,))

    def __repr__(self):
        return ":".join(['dcp', 'upl', 'aws', self.deployment_stage, self.uuid])

    @property
    def credentials(self):
        uppercase_credentials = json.loads(base64.b64decode(self.encoded_credentials).decode('ascii'))
        return {k.lower(): v for k, v in uppercase_credentials.items()}


class TestUploadService(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch = boto3.client('batch')

    def setUp(self):
        self.deployment_stage = os.environ['DEPLOYMENT_STAGE']
        self.auth_headers = {'Api-Key': os.environ['INGEST_API_KEY']}
        self.api_url = f"https://{os.environ['API_HOST']}/v1"
        self.verbose = True

    def testIt(self):
        print(f"\n\nUsing environment {self.deployment_stage} at URL {self.api_url}.\n")

        self.upload_area_id = "deadbeef-dead-dead-dead-%012d" % random.randint(0, 999999999999)
        filename = 'LICENSE'

        self._create_upload_area()
        self._upload_file_using_cli(filename)
        self._verify_file_is_checksummed(filename)
        self._validate_file(filename)
        self._forget_upload_area()
        self._delete_upload_area()

    def _create_upload_area(self):
        response = self._make_request(description="CREATE UPLOAD AREA",
                                      verb='POST',
                                      url=f"{self.api_url}/area/{self.upload_area_id}",
                                      headers=self.auth_headers,
                                      expected_status=201)
        data = json.loads(response)
        self.urn = UploadAreaURN(data['urn'])
        self.assertEqual('UNLOCKED', self._upload_area_record_status())

    def _upload_file_using_cli(self, filename):
        self._run("SELECT UPLOAD AREA", ['hca', 'upload', 'select', self.urn.urn])
        self._run("UPLOAD FILE USING CLI", ['hca', 'upload', 'file', filename])

    def _verify_file_is_checksummed(self, filename):
        WaitFor(self._checksum_record_status, filename)\
            .to_return_value('SCHEDULED', timeout_seconds=30)

        csum_record = self._checksum_record(filename)
        WaitFor(self._batch_job_status, csum_record.job_id)\
            .to_return_value('SUCCEEDED', timeout_seconds=20 * MINUTE_SEC)

        self.assertEqual('CHECKSUMMED', self._checksum_record_status(filename))

        # TODO: pull checksums out of S3 and check them

    def _validate_file(self, filename):
        response = self._make_request(description="VALIDATE",
                                      verb='PUT',
                                      url=f"{self.api_url}/area/{self.upload_area_id}/{filename}/validate",
                                      expected_status=200,
                                      headers=self.auth_headers,
                                      json={"validator_image": "humancellatlas/upload-validator-example"})
        validation_job_id = json.loads(response)['validation_id']

        WaitFor(self._batch_job_status, validation_job_id)\
            .to_return_value('SUCCEEDED', timeout_seconds=20 * MINUTE_SEC)

        WaitFor(self._validation_record_status, validation_job_id)\
            .to_return_value('VALIDATED', timeout_seconds=MINUTE_SEC)

        # TODO: check validation results

    def _forget_upload_area(self):
        self._run("FORGET UPLOAD AREA", ['hca', 'upload', 'forget', self.urn.uuid])

    def _delete_upload_area(self):
        self._make_request(description="DELETE UPLOAD AREA",
                           verb='DELETE',
                           url=f"{self.api_url}/area/{self.upload_area_id}",
                           headers=self.auth_headers,
                           expected_status=204)
        self.assertEqual('DELETED', self._upload_area_record_status())

    def _upload_area_record_status(self):
        record = self._upload_area_record()
        return record.status if record else None

    def _checksum_record_status(self, filename):
        record = self._checksum_record(filename)
        return record.status if record else None

    def _validation_record_status(self, validation_job_id):
        record = self._validation_record(validation_job_id)
        return record.status if record else None

    def _upload_area_record(self):
        db = db_session_maker()()
        return db.query(DbUploadArea).filter(DbUploadArea.id == self.upload_area_id).one_or_none()

    def _checksum_record(self, filename):
        db = db_session_maker()()
        file_id = f"{self.upload_area_id}/{filename}"
        record = db.query(DbChecksum).filter(DbChecksum.file_id == file_id).one_or_none()
        return record

    def _validation_record(self, validation_job_id):
        db = db_session_maker()()
        return db.query(DbValidation).filter(DbValidation.job_id == validation_job_id).one_or_none()

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
        print("\n", description + ": ")
        print(' '.join(command))
        completed_process = subprocess.run(command, stdout=None, stderr=None)
        self.assertEqual(expected_returncode, completed_process.returncode)
