#!/usr/bin/env python3.6

import os, sys, unittest, uuid, json, base64
from unittest.mock import patch

import boto3
from botocore.exceptions import ClientError

from . import client_for_test_api_server
from ... import UploadTestCaseUsingMockAWS, EnvironmentSetup

from upload.common.checksum_event import UploadedFileChecksumEvent
from upload.common.validation_event import UploadedFileValidationEvent
from upload.common.uploaded_file import UploadedFile
from upload.common.upload_area import UploadArea
from upload.common.database import get_pg_record

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa


class TestApiAuthenticationErrors(UploadTestCaseUsingMockAWS):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Setup app
        with EnvironmentSetup({
            'BUCKET_NAME': "bogobucket",
            'DEPLOYMENT_STAGE': 'test',
            'INGEST_API_KEY': 'unguessable'
        }):
            self.client = client_for_test_api_server()

    def test_call_without_auth_setup(self):
        # Use a different app instance started without an INGEST_API_KEY
        with EnvironmentSetup({
            'BUCKET_NAME': "bogobucket",
            'DEPLOYMENT_STAGE': 'test',
            'INGEST_API_KEY': None
        }):
            self.client = client_for_test_api_server()

            response = self.client.post(f"/v1/area/{str(uuid.uuid4())}", headers={'Api-Key': 'foo'})

        self.assertEqual(response.status_code, 500)
        self.assertIn("INGEST_API_KEY", response.data.decode('utf8'))

    def test_call_with_unautenticated(self):

        response = self.client.post(f"/v1/area/{str(uuid.uuid4())}")

        self.assertEqual(response.status_code, 400)
        self.assertRegex(str(response.data), "Missing header.*Api-Key")

    def test_call_with_bad_api_key(self):

        response = self.client.post(f"/v1/area/{str(uuid.uuid4())}", headers={'Api-Key': 'I-HAXX0RED-U'})

        self.assertEqual(response.status_code, 401)


class TestAreaApi(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        # Environment
        self.deployment_stage = 'test'
        self.upload_bucket_name = f'bogobucket'
        self.api_key = "foo"
        self.environment = {
            'BUCKET_NAME': self.upload_bucket_name,
            'DEPLOYMENT_STAGE': self.deployment_stage,
            'DCP_EVENTS_TOPIC': 'bogotopic',
            'INGEST_API_KEY': self.api_key,
            'INGEST_AMQP_SERVER': 'foo',
            'CSUM_JOB_Q_ARN': 'bogoqarn',
            'CSUM_JOB_ROLE_ARN': 'bogorolearn',
            'CSUM_DOCKER_IMAGE': 'bogoimage'
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()
        # Setup upload bucket
        self.upload_bucket = boto3.resource('s3').Bucket(self.upload_bucket_name)
        self.upload_bucket.create()
        # Authentication
        self.authentication_header = {'Api-Key': self.api_key}
        # Setup SNS
        boto3.resource('sns').create_topic(Name='bogotopic')
        # Setup app
        self.client = client_for_test_api_server()

    def tearDown(self):
        super().tearDown()
        self.environmentor.exit()

    @patch('upload.common.upload_area.UploadArea.IAM_SETTLE_TIME_SEC', 0)
    def _create_area(self):
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)
        return area_id

    def _mock_upload_file(self, area_id, filename, contents="foo", content_type="application/json",
                          checksums=None):
        checksums = {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'} if not checksums else checksums
        file1_key = f"{area_id}/{filename}"
        s3obj = self.upload_bucket.Object(file1_key)
        s3obj.put(Body=contents, ContentType=content_type)
        boto3.client('s3').put_object_tagging(Bucket=self.upload_bucket_name, Key=file1_key, Tagging={
            'TagSet': [
                {'Key': 'hca-dss-content-type', 'Value': content_type},
                {'Key': 'hca-dss-s3_etag', 'Value': checksums['s3_etag']},
                {'Key': 'hca-dss-sha1', 'Value': checksums['sha1']},
                {'Key': 'hca-dss-sha256', 'Value': checksums['sha256']},
                {'Key': 'hca-dss-crc32c', 'Value': checksums['crc32c']}
            ]
        })
        return s3obj

    @patch('upload.common.upload_area.UploadArea.IAM_SETTLE_TIME_SEC', 0)
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.connect')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_update_file_checksum(self, mock_format_and_send_notification, mock_connect):
        checksum_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self._mock_upload_file(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3obj)
        uploaded_file.create_record()
        checksum_event = UploadedFileChecksumEvent(file_id=s3obj.key,
                                                   checksum_id=checksum_id,
                                                   job_id='12345',
                                                   status="SCHEDULED")
        checksum_event.create_record()

        data = {
            "status": "CHECKSUMMING",
            "job_id": checksum_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_id}/update_checksum/{checksum_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(response.status_code, 204)
        record = get_pg_record("checksum", checksum_id)
        self.assertEqual(record["status"], "CHECKSUMMING")
        self.assertEqual(str(type(record.get("checksum_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(record["checksum_ended_at"], None)
        mock_format_and_send_notification.assert_not_called()

        data = {
            "status": "CHECKSUMMED",
            "job_id": checksum_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_id}/update_checksum/{checksum_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(response.status_code, 204)
        mock_format_and_send_notification.assert_called_once_with({
            'upload_area_id': area_id,
            'name': 'foo.json',
            'size': 3,
            'last_modified': s3obj.last_modified.isoformat(),
            'content_type': "application/json",
            'url': f"s3://{self.upload_bucket_name}/{area_id}/foo.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        record = get_pg_record("checksum", checksum_id)
        self.assertEqual(record["status"], "CHECKSUMMED")
        self.assertEqual(str(type(record.get("checksum_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(str(type(record.get("checksum_ended_at"))), "<class 'datetime.datetime'>")

    @patch('upload.common.upload_area.UploadArea.IAM_SETTLE_TIME_SEC', 0)
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.connect')
    @patch('upload.lambdas.checksum_daemon.checksum_daemon.IngestNotifier.format_and_send_notification')
    def test_update_file_validation(self, mock_format_and_send_notification, mock_connect):
        validation_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self._mock_upload_file(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3obj)
        uploaded_file.create_record()
        validation_event = UploadedFileValidationEvent(file_id=s3obj.key,
                                                       validation_id=validation_id,
                                                       job_id='12345',
                                                       status="SCHEDULED")
        validation_event.create_record()
        data = {
            "status": "VALIDATING",
            "job_id": validation_event.job_id,
            "payload": uploaded_file.info()
        }

        response = self.client.post(f"/v1/area/{area_id}/update_validation/{validation_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(response.status_code, 204)
        record = get_pg_record("validation", validation_id)
        self.assertEqual(record["status"], "VALIDATING")
        self.assertEqual(str(type(record.get("validation_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(record["validation_ended_at"], None)
        mock_format_and_send_notification.assert_not_called()

        data = {
            "status": "VALIDATED",
            "job_id": validation_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_id}/update_validation/{validation_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(response.status_code, 204)
        mock_format_and_send_notification.assert_called_once_with({
            'upload_area_id': area_id,
            'name': 'foo.json',
            'size': 3,
            'last_modified': s3obj.last_modified.isoformat(),
            'content_type': "application/json",
            'url': f"s3://{self.upload_bucket_name}/{area_id}/foo.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        record = get_pg_record("validation", validation_id)
        self.assertEqual(record["status"], "VALIDATED")
        self.assertEqual(str(type(record.get("validation_started_at"))), "<class 'datetime.datetime'>")
        self.assertEqual(str(type(record.get("validation_ended_at"))), "<class 'datetime.datetime'>")

    @patch('upload.common.upload_area.UploadArea.IAM_SETTLE_TIME_SEC', 0)
    def test_create_with_unused_upload_area_id(self):
        area_id = str(uuid.uuid4())

        response = self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(response.status_code, 201)
        body = json.loads(response.data)
        self.assertEqual(list(body.keys()), ['urn'])
        urnbits = body['urn'].split(':')
        self.assertEqual(len(urnbits), 6)  # dcp:upl:aws:dev:uuid:encoded-creds
        self.assertEqual(urnbits[0:4], ['dcp', 'upl', 'aws', 'test'])
        self.assertEqual(urnbits[4], area_id)
        creds = json.loads(base64.b64decode(urnbits[5].encode('utf8')))
        self.assertEqual(list(creds.keys()), ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'])

        try:
            user_name = f"upload-{self.deployment_stage}-user-{area_id}"
            user = boto3.resource('iam').User(user_name)
            user.load()
        except ClientError:
            self.fail("Staging area (user) was not created!")
        policy = user.Policy(f"upload-{area_id}")
        self.assertIn('{"Effect": "Allow", "Action": ["s3:PutObject"', policy.policy_document)
        self.assertIn(f'"Resource": ["arn:aws:s3:::{self.upload_bucket_name}/{area_id}/*"]',
                      policy.policy_document)
        record = get_pg_record("upload_area", area_id)
        self.assertEqual(record["status"], "UNLOCKED")

    @patch('upload.common.upload_area.UploadArea.IAM_SETTLE_TIME_SEC', 0)
    def test_create_in_production_returns_5_part_urn(self):
        prod_env = dict(self.environment)
        prod_env['DEPLOYMENT_STAGE'] = 'prod'
        with EnvironmentSetup(prod_env):

            area_id = str(uuid.uuid4())

            response = self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

            self.assertEqual(response.status_code, 201)
            body = json.loads(response.data)
            self.assertEqual(list(body.keys()), ['urn'])
            urnbits = body['urn'].split(':')
            self.assertEqual(len(urnbits), 5)  # dcp:upl:aws:uuid:encoded-creds
            self.assertEqual(urnbits[0:3], ['dcp', 'upl', 'aws'])
            self.assertEqual(urnbits[3], area_id)
            creds = json.loads(base64.b64decode(urnbits[4].encode('utf8')))
            self.assertEqual(list(creds.keys()), ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'])

    def test_create_with_already_used_upload_area_id(self):
        area_id = str(uuid.uuid4())
        user_name = f"upload-{self.deployment_stage}-user-{area_id}"
        boto3.resource('iam').User(user_name).create()

        response = self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.content_type, 'application/problem+json')

    def test_delete_with_id_of_real_non_empty_upload_area(self):
        area_id = str(uuid.uuid4())
        user = boto3.resource('iam').User(f"upload-{self.deployment_stage}-user-{area_id}")
        user.create()
        bucket = boto3.resource('s3').Bucket(self.upload_bucket_name)
        bucket.create()
        obj = bucket.Object(f'{area_id}/test_file')
        obj.put(Body="foo")

        response = self.client.delete(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(response.status_code, 204)
        with self.assertRaises(ClientError):
            user.load()
        with self.assertRaises(ClientError):
            obj.load()

    def test_delete_with_unused_used_upload_area_id(self):
        area_id = str(uuid.uuid4())

        response = self.client.delete(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content_type, 'application/problem+json')

    @patch('upload.common.upload_area.UploadArea.IAM_SETTLE_TIME_SEC', 0)
    def test_locking_of_upload_area(self):
        area_id = self._create_area()
        user_name = f"upload-{self.deployment_stage}-user-" + area_id
        policy_name = 'upload-' + area_id
        policy = boto3.resource('iam').UserPolicy(user_name, policy_name)
        self.assertIn('{"Effect": "Allow", "Action": ["s3:PutObject"', policy.policy_document)
        record = get_pg_record("upload_area", area_id)
        self.assertEqual(record["status"], "UNLOCKED")

        response = self.client.post(f"/v1/area/{area_id}/lock", headers=self.authentication_header)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(list(boto3.resource('iam').User(user_name).policies.all())), 0)
        record = get_pg_record("upload_area", area_id)
        self.assertEqual(record["status"], "LOCKED")

        response = self.client.delete(f"/v1/area/{area_id}/lock", headers=self.authentication_header)

        self.assertEqual(response.status_code, 204)
        record = get_pg_record("upload_area", area_id)
        self.assertEqual(record["status"], "UNLOCKED")

        policy = boto3.resource('iam').UserPolicy(user_name, policy_name)
        self.assertIn('{"Effect": "Allow", "Action": ["s3:PutObject"', policy.policy_document)

    def test_put_file_without_content_type_dcp_type_param(self):
        headers = {'Content-Type': 'application/json'}
        headers.update(self.authentication_header)
        area_id = self._create_area()

        response = self.client.put(f"/v1/area/{area_id}/some.json", data="exquisite corpse", headers=headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content_type, 'application/problem+json')
        self.assertIn("missing parameter \'dcp-type\'", response.data.decode('utf8'))

    def test_put_file(self):
        headers = {'Content-Type': 'application/json; dcp-type="metadata/sample"'}
        headers.update(self.authentication_header)
        area_id = self._create_area()

        response = self.client.put(f"/v1/area/{area_id}/some.json", data="exquisite corpse", headers=headers)

        s3_key = f"{area_id}/some.json"
        o1 = self.upload_bucket.Object(s3_key)
        o1.load()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(json.loads(response.data), {
            'upload_area_id': area_id,
            'name': 'some.json',
            'size': 16,
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/sample"',
            'url': f"s3://{self.upload_bucket_name}/{area_id}/some.json",
            'checksums': {
                "crc32c": "FE9ADA52",
                "s3_etag": "18f17fbfdd21cf869d664731e10d4ffd",
                "sha1": "b1b101e21cf9cf8a4729da44d7818f935eec0ce8",
                "sha256": "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70"
            }
        })
        obj = self.upload_bucket.Object(f"{area_id}/some.json")
        self.assertEqual(obj.get()['Body'].read(), "exquisite corpse".encode('utf8'))

        record = get_pg_record("file", s3_key)
        self.assertEqual(record["size"], 16)
        self.assertEqual(record["upload_area_id"], area_id)
        self.assertEqual(record["name"], "some.json")

    def test_list_files(self):
        area_id = self._create_area()
        o1 = self._mock_upload_file(area_id, 'file1.json', content_type='application/json; dcp-type="metadata/foo"')
        o2 = self._mock_upload_file(area_id, 'file2.fastq.gz',
                                    content_type='application/octet-stream; dcp-type=data',
                                    checksums={'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'})

        response = self.client.get(f"/v1/area/{area_id}")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('size', data['files'][0].keys())  # moto file sizes are not accurate
        for fileinfo in data['files']:
            del fileinfo['size']
        self.assertEqual(data['files'][0], {
            'upload_area_id': area_id,
            'name': 'file1.json',
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/foo"',
            'url': f"s3://{self.upload_bucket_name}/{area_id}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        self.assertEqual(data['files'][1], {
            'upload_area_id': area_id,
            'name': 'file2.fastq.gz',
            'last_modified': o2.last_modified.isoformat(),
            'content_type': 'application/octet-stream; dcp-type=data',
            'url': f"s3://{self.upload_bucket_name}/{area_id}/file2.fastq.gz",
            'checksums': {'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'}
        })

    def test_list_files_only_lists_files_in_my_upload_area(self):
        area1_id = self._create_area()
        area2_id = self._create_area()
        area_1_files = ['file1', 'file2']
        area_2_files = ['file3', 'file4']
        [self._mock_upload_file(area1_id, file) for file in area_1_files]
        [self._mock_upload_file(area2_id, file) for file in area_2_files]

        response = self.client.get(f"/v1/area/{area2_id}")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual([file['name'] for file in data['files']], area_2_files)

    def test_get_file_for_existing_file(self):
        area_id = self._create_area()
        filename = 'file1.json'
        s3obj = self._mock_upload_file(area_id, filename)

        response = self.client.get(f"/v1/area/{area_id}/{filename}")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('size', data.keys())  # moto file sizes are not accurate
        del data['size']
        self.assertEqual(data, {
            'upload_area_id': area_id,
            'name': 'file1.json',
            'last_modified': s3obj.last_modified.isoformat(),
            'content_type': 'application/json',
            'url': f"s3://{self.upload_bucket_name}/{area_id}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })

    @patch('upload.common.upload_area.UploadArea.IAM_SETTLE_TIME_SEC', 0)
    def test_get_file_returns_404_for_missing_area_or_file(self):
        response = self.client.get(f"/v1/area/bogoarea/bogofile")
        self.assertEqual(response.status_code, 404)

        area_id = str(uuid.uuid4())

        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        response = self.client.get(f"/v1/area/{area_id}/bogofile")
        self.assertEqual(response.status_code, 404)

    def test_put_files_info(self):
        area_id = self._create_area()
        o1 = self._mock_upload_file(area_id, 'file1.json', content_type='application/json; dcp-type="metadata/foo"')
        o2 = self._mock_upload_file(area_id, 'file2.fastq.gz',
                                    content_type='application/octet-stream; dcp-type=data',
                                    checksums={'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'})
        self._mock_upload_file(area_id, 'a_file_in_the_same_area_that_we_will_not_attempt_to_list')

        response = self.client.put(f"/v1/area/{area_id}/files_info", content_type='application/json',
                                   data=(json.dumps(['file1.json', 'file2.fastq.gz'])))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)

        self.assertIn('size', data[0].keys())  # moto file sizes are not accurate
        for fileinfo in data:
            del fileinfo['size']

        self.assertEqual(data[0], {
            'upload_area_id': area_id,
            'name': 'file1.json',
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/foo"',
            'url': f"s3://{self.upload_bucket_name}/{area_id}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        self.assertEqual(data[1], {
            'upload_area_id': area_id,
            'name': 'file2.fastq.gz',
            'last_modified': o2.last_modified.isoformat(),
            'content_type': 'application/octet-stream; dcp-type=data',
            'url': f"s3://{self.upload_bucket_name}/{area_id}/file2.fastq.gz",
            'checksums': {'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'}
        })


if __name__ == '__main__':
    unittest.main()
