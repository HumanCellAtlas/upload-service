#!/usr/bin/env python3.6

import os, sys, unittest, uuid, json

import boto3
from botocore.exceptions import ClientError

from . import client_for_test_api_server
from ... import UploadTestCaseUsingMockAWS, EnvironmentSetup

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
            'DEPLOYMENT_STAGE': 'test',
            'INGEST_API_KEY': 'unguessable'
        }):
            self.client = client_for_test_api_server()

    def test_call_without_auth_setup(self):
        # Use a different app instance started without an INGEST_API_KEY
        with EnvironmentSetup({
            'DEPLOYMENT_STAGE': 'test',
            'INGEST_API_KEY': None
        }):
            self.client = client_for_test_api_server()

            response = self.client.post(f"/v1/area/{str(uuid.uuid4())}", headers={'Api-Key': 'foo'})

        self.assertEqual(500, response.status_code)
        self.assertIn("INGEST_API_KEY", response.data.decode('utf8'))

    def test_call_with_unautenticated(self):

        response = self.client.post(f"/v1/area/{str(uuid.uuid4())}")

        self.assertEqual(400, response.status_code)
        self.assertRegex(str(response.data), "Missing header.*Api-Key")

    def test_call_with_bad_api_key(self):

        response = self.client.post(f"/v1/area/{str(uuid.uuid4())}", headers={'Api-Key': 'I-HAXX0RED-U'})

        self.assertEqual(401, response.status_code)


class TestAreaApi(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        # Environment
        self.api_key = "foo"
        self.environment = {
            'INGEST_API_KEY': self.api_key,
            'INGEST_AMQP_SERVER': 'foo',
            'CSUM_DOCKER_IMAGE': 'bogo_image',
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()

        # Authentication
        self.authentication_header = {'Api-Key': self.api_key}
        # Setup app
        self.client = client_for_test_api_server()

    def tearDown(self):
        super().tearDown()
        self.environmentor.exit()

    def _create_area(self):
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)
        return area_id

    def test_head_upload_area_does_not_exist(self):
        area_id = str(uuid.uuid4())
        response = self.client.head(f"/v1/area/{area_id}")
        self.assertEqual(response.status_code, 404)

    def test_head_upload_area_does_exist(self):
        area_id = self._create_area()
        response = self.client.head(f"/v1/area/{area_id}")
        self.assertEqual(response.status_code, 200)

    def test_create_with_unused_upload_area_id(self):
        area_id = str(uuid.uuid4())

        response = self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(201, response.status_code)
        body = json.loads(response.data)
        self.assertEqual(
            {'uri': f"s3://{self.upload_config.bucket_name}/{area_id}/"},
            body)

        record = get_pg_record("upload_area", area_id)
        self.assertEqual(area_id, record["id"])
        self.assertEqual(self.upload_config.bucket_name, record["bucket_name"])
        self.assertEqual("UNLOCKED", record["status"])

    def test_create_with_already_used_upload_area_id(self):
        area_id = self._create_area()

        response = self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(201, response.status_code)
        body = json.loads(response.data)
        self.assertEqual(
            {'uri': f"s3://{self.upload_config.bucket_name}/{area_id}/"},
            body)

        record = get_pg_record("upload_area", area_id)
        self.assertEqual(area_id, record["id"])
        self.assertEqual(self.upload_config.bucket_name, record["bucket_name"])
        self.assertEqual("UNLOCKED", record["status"])

    def test_credentials_with_non_existent_upload_area(self):
        area_id = str(uuid.uuid4())

        response = self.client.post(f"/v1/area/{area_id}/credentials")

        self.assertEqual(404, response.status_code)

    def test_credentials_with_existing_locked_upload_area(self):
        area_id = self._create_area()
        UploadArea(area_id).lock()

        response = self.client.post(f"/v1/area/{area_id}/credentials")

        self.assertEqual(409, response.status_code)

    def test_credentials_with_deleted_upload_area(self):
        area_id = self._create_area()
        UploadArea(area_id).delete()

        response = self.client.post(f"/v1/area/{area_id}/credentials")

        self.assertEqual(404, response.status_code)

    def test_credentials_with_existing_unlocked_upload_area(self):
        area_id = self._create_area()

        response = self.client.post(f"/v1/area/{area_id}/credentials")

        data = json.loads(response.data)
        self.assertEqual(['AccessKeyId', 'Expiration', 'SecretAccessKey', 'SessionToken'], list(data.keys()))

    def test_delete_with_id_of_real_non_empty_upload_area(self):
        area_id = self._create_area()

        obj = self.upload_bucket.Object(f'{area_id}/test_file')
        obj.put(Body="foo")

        response = self.client.delete(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(204, response.status_code)
        record = get_pg_record("upload_area", area_id)
        self.assertEqual("DELETED", record["status"])
        with self.assertRaises(ClientError):
            obj.load()

    def test_delete_with_unused_used_upload_area_id(self):
        area_id = str(uuid.uuid4())

        response = self.client.delete(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(404, response.status_code)
        self.assertEqual('application/problem+json', response.content_type)

    def test_locking_of_upload_area(self):
        area_id = self._create_area()
        record = get_pg_record("upload_area", area_id)
        self.assertEqual("UNLOCKED", record["status"])

        response = self.client.post(f"/v1/area/{area_id}/lock", headers=self.authentication_header)

        self.assertEqual(204, response.status_code)
        record = get_pg_record("upload_area", area_id)
        self.assertEqual("LOCKED", record["status"])

        response = self.client.delete(f"/v1/area/{area_id}/lock", headers=self.authentication_header)

        self.assertEqual(204, response.status_code)
        record = get_pg_record("upload_area", area_id)
        self.assertEqual("UNLOCKED", record["status"])

    def test_put_file_without_content_type_dcp_type_param(self):
        headers = {'Content-Type': 'application/json'}
        headers.update(self.authentication_header)
        area_id = self._create_area()

        response = self.client.put(f"/v1/area/{area_id}/some.json", data="exquisite corpse", headers=headers)

        self.assertEqual(400, response.status_code)
        self.assertEqual('application/problem+json', response.content_type)
        self.assertIn("missing parameter \'dcp-type\'", response.data.decode('utf8'))

    def test_put_file(self):
        headers = {'Content-Type': 'application/json; dcp-type="metadata/sample"'}
        headers.update(self.authentication_header)
        area_id = self._create_area()

        response = self.client.put(f"/v1/area/{area_id}/some.json", data="exquisite corpse", headers=headers)

        s3_key = f"{area_id}/some.json"
        o1 = self.upload_bucket.Object(s3_key)
        o1.load()
        self.assertEqual(201, response.status_code)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(json.loads(response.data), {
            'upload_area_id': area_id,
            'name': 'some.json',
            'size': 16,
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/sample"',
            'url': f"s3://{self.upload_config.bucket_name}/{area_id}/some.json",
            'checksums': {
                "crc32c": "FE9ADA52",
                "s3_etag": "18f17fbfdd21cf869d664731e10d4ffd",
                "sha1": "b1b101e21cf9cf8a4729da44d7818f935eec0ce8",
                "sha256": "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70"
            }
        })
        obj = self.upload_bucket.Object(f"{area_id}/some.json")
        self.assertEqual("exquisite corpse".encode('utf8'), obj.get()['Body'].read())

        record = get_pg_record("file", s3_key)
        self.assertEqual(16, record["size"])
        self.assertEqual(area_id, record["upload_area_id"])
        self.assertEqual("some.json", record["name"])

    def test_list_files(self):
        area_id = self._create_area()
        o1 = self.mock_upload_file(area_id, 'file1.json', content_type='application/json; dcp-type="metadata/foo"')
        o2 = self.mock_upload_file(area_id, 'file2.fastq.gz',
                                   content_type='application/octet-stream; dcp-type=data',
                                   checksums={'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'})

        response = self.client.get(f"/v1/area/{area_id}")

        self.assertEqual(200, response.status_code)
        data = json.loads(response.data)
        self.assertIn('size', data['files'][0].keys())  # moto file sizes are not accurate
        for fileinfo in data['files']:
            del fileinfo['size']
        self.assertEqual(data['files'][0], {
            'upload_area_id': area_id,
            'name': 'file1.json',
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/foo"',
            'url': f"s3://{self.upload_config.bucket_name}/{area_id}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        self.assertEqual(data['files'][1], {
            'upload_area_id': area_id,
            'name': 'file2.fastq.gz',
            'last_modified': o2.last_modified.isoformat(),
            'content_type': 'application/octet-stream; dcp-type=data',
            'url': f"s3://{self.upload_config.bucket_name}/{area_id}/file2.fastq.gz",
            'checksums': {'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'}
        })

    def test_list_files_only_lists_files_in_my_upload_area(self):
        area1_id = self._create_area()
        area2_id = self._create_area()
        area_1_files = ['file1', 'file2']
        area_2_files = ['file3', 'file4']
        [self.mock_upload_file(area1_id, file) for file in area_1_files]
        [self.mock_upload_file(area2_id, file) for file in area_2_files]

        response = self.client.get(f"/v1/area/{area2_id}")

        self.assertEqual(200, response.status_code)
        data = json.loads(response.data)
        self.assertEqual(area_2_files, [file['name'] for file in data['files']])

    def test_get_file_for_existing_file(self):
        area_id = self._create_area()
        filename = 'file1.json'
        s3obj = self.mock_upload_file(area_id, filename)

        response = self.client.get(f"/v1/area/{area_id}/{filename}")

        self.assertEqual(200, response.status_code)
        data = json.loads(response.data)
        self.assertIn('size', data.keys())  # moto file sizes are not accurate
        del data['size']
        self.assertEqual(data, {
            'upload_area_id': area_id,
            'name': 'file1.json',
            'last_modified': s3obj.last_modified.isoformat(),
            'content_type': 'application/json',
            'url': f"s3://{self.upload_config.bucket_name}/{area_id}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })

    def test_get_file_returns_404_for_missing_area_or_file(self):
        response = self.client.get(f"/v1/area/bogoarea/bogofile")
        self.assertEqual(404, response.status_code)

        area_id = str(uuid.uuid4())

        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        response = self.client.get(f"/v1/area/{area_id}/bogofile")
        self.assertEqual(404, response.status_code)

    def test_put_files_info(self):
        area_id = self._create_area()
        o1 = self.mock_upload_file(area_id, 'file1.json', content_type='application/json; dcp-type="metadata/foo"')
        o2 = self.mock_upload_file(area_id, 'file2.fastq.gz',
                                   content_type='application/octet-stream; dcp-type=data',
                                   checksums={'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'})
        self.mock_upload_file(area_id, 'a_file_in_the_same_area_that_we_will_not_attempt_to_list')

        response = self.client.put(f"/v1/area/{area_id}/files_info", content_type='application/json',
                                   data=(json.dumps(['file1.json', 'file2.fastq.gz'])))

        self.assertEqual(200, response.status_code)
        data = json.loads(response.data)
        self.assertEqual(2, len(data))

        self.assertIn('size', data[0].keys())  # moto file sizes are not accurate
        for fileinfo in data:
            del fileinfo['size']

        self.assertEqual(data[0], {
            'upload_area_id': area_id,
            'name': 'file1.json',
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/foo"',
            'url': f"s3://{self.upload_config.bucket_name}/{area_id}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        self.assertEqual(data[1], {
            'upload_area_id': area_id,
            'name': 'file2.fastq.gz',
            'last_modified': o2.last_modified.isoformat(),
            'content_type': 'application/octet-stream; dcp-type=data',
            'url': f"s3://{self.upload_config.bucket_name}/{area_id}/file2.fastq.gz",
            'checksums': {'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'}
        })

    def test_post_file_with_valid_area(self):
        area_id = self._create_area()

        response = self.client.post(f"/v1/area/{area_id}/filename123")
        message = self.sqs.meta.client.receive_message(QueueUrl='bogo_url')

        message_body = json.loads(message['Messages'][0]['Body'])
        s3_key = message_body['Records'][0]['s3']['object']['key']
        s3_bucket = message_body['Records'][0]['s3']['bucket']['name']
        self.assertEqual(202, response.status_code)
        self.assertEqual(s3_key, f"{area_id}/filename123")
        self.assertEqual(s3_bucket, "bogobucket")

    def test_post_file_with_invalid_area(self):
        area_id = str(uuid.uuid4())
        response = self.client.post(f"/v1/area/{area_id}/filename123")
        self.assertEqual(404, response.status_code)

    def test_add_uploaded_file_to_csum_daemon_sqs(self):
        area_id = self._create_area()

        UploadArea(area_id).add_uploaded_file_to_csum_daemon_sqs("filename123")
        message = self.sqs.meta.client.receive_message(QueueUrl='bogo_url')

        message_body = json.loads(message['Messages'][0]['Body'])
        s3_key = message_body['Records'][0]['s3']['object']['key']
        s3_bucket = message_body['Records'][0]['s3']['bucket']['name']
        self.assertEqual(s3_key, f"{area_id}/filename123")
        self.assertEqual(s3_bucket, "bogobucket")


if __name__ == '__main__':
    unittest.main()
