#!/usr/bin/env python3.6

import os, sys, unittest, uuid, json

from botocore.exceptions import ClientError

from moto import mock_sts
from mock import patch

from . import client_for_test_api_server
from ... import UploadTestCaseUsingMockAWS, EnvironmentSetup

from upload.common.upload_area import UploadArea, lambda_client
from upload.common.database import UploadDB

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
        area_uuid = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_uuid}", headers=self.authentication_header)
        return area_uuid

    def test_head_upload_area_does_not_exist(self):
        area_uuid = str(uuid.uuid4())
        response = self.client.head(f"/v1/area/{area_uuid}")
        self.assertEqual(response.status_code, 404)

    def test_head_upload_area_does_exist(self):
        area_uuid = self._create_area()
        response = self.client.head(f"/v1/area/{area_uuid}")
        self.assertEqual(response.status_code, 200)

    def test_create_with_unused_upload_area_uuid(self):
        area_uuid = str(uuid.uuid4())

        response = self.client.post(f"/v1/area/{area_uuid}", headers=self.authentication_header)

        self.assertEqual(201, response.status_code)
        body = json.loads(response.data)
        self.assertEqual(
            {'uri': f"s3://{self.upload_config.bucket_name}/{area_uuid}/"},
            body)

        record = UploadDB().get_pg_record("upload_area", area_uuid, column='uuid')
        self.assertEqual(area_uuid, record["uuid"])
        self.assertEqual(self.upload_config.bucket_name, record["bucket_name"])
        self.assertEqual("UNLOCKED", record["status"])

    def test_create_with_already_used_upload_area_uuid(self):
        area_uuid = self._create_area()

        response = self.client.post(f"/v1/area/{area_uuid}", headers=self.authentication_header)

        self.assertEqual(201, response.status_code)
        body = json.loads(response.data)
        self.assertEqual(
            {'uri': f"s3://{self.upload_config.bucket_name}/{area_uuid}/"},
            body)

        record = UploadDB().get_pg_record("upload_area", area_uuid, column='uuid')
        self.assertEqual(area_uuid, record["uuid"])
        self.assertEqual(self.upload_config.bucket_name, record["bucket_name"])
        self.assertEqual("UNLOCKED", record["status"])

    @mock_sts
    def test_credentials_with_non_existent_upload_area(self):
        area_uuid = str(uuid.uuid4())

        response = self.client.post(f"/v1/area/{area_uuid}/credentials")

        self.assertEqual(404, response.status_code)

    @mock_sts
    def test_credentials_with_existing_locked_upload_area(self):
        area_uuid = self._create_area()
        UploadArea(area_uuid).lock()

        response = self.client.post(f"/v1/area/{area_uuid}/credentials")

        self.assertEqual(409, response.status_code)

    @mock_sts
    @patch('upload.common.upload_area.UploadArea._retrieve_upload_area_deletion_lambda_timeout')
    def test_credentials_with_deleted_upload_area(self, mock_area_deletion_timeout):
        area_uuid = self._create_area()
        mock_area_deletion_timeout.return_value = 900
        UploadArea(area_uuid).delete()

        response = self.client.post(f"/v1/area/{area_uuid}/credentials")

        self.assertEqual(404, response.status_code)

    @mock_sts
    def test_credentials_with_existing_unlocked_upload_area(self):
        area_uuid = self._create_area()

        response = self.client.post(f"/v1/area/{area_uuid}/credentials")

        data = json.loads(response.data)
        self.assertEqual(['AccessKeyId', 'Expiration', 'SecretAccessKey', 'SessionToken'], list(data.keys()))

    def test_delete_with_id_of_real_non_empty_upload_area(self):
        area_uuid = self._create_area()

        obj = self.upload_bucket.Object(f'{area_uuid}/test_file')
        obj.put(Body="foo")

        response = self.client.delete(f"/v1/area/{area_uuid}", headers=self.authentication_header)

        self.assertEqual(202, response.status_code)
        record = UploadDB().get_pg_record("upload_area", area_uuid, column='uuid')
        self.assertEqual("DELETION_QUEUED", record["status"])

    @patch('upload.common.upload_area.UploadArea._retrieve_upload_area_deletion_lambda_timeout')
    def test_upload_area_delete(self, mock_retrieve_lambda_timeout):
        area_uuid = self._create_area()
        obj = self.upload_bucket.Object(f'{area_uuid}/test_file')
        obj.put(Body="foo")
        mock_retrieve_lambda_timeout.return_value = 900

        area = UploadArea(area_uuid)
        area.delete()

        record = UploadDB().get_pg_record("upload_area", area_uuid, column='uuid')
        self.assertEqual("DELETED", record["status"])
        with self.assertRaises(ClientError):
            obj.load()

    @patch('upload.common.upload_area.UploadArea._retrieve_upload_area_deletion_lambda_timeout')
    def test_upload_area_delete_over_timeout(self, mock_retrieve_lambda_timeout):
        area_uuid = self._create_area()
        obj = self.upload_bucket.Object(f'{area_uuid}/test_file')
        obj.put(Body="foo")
        mock_retrieve_lambda_timeout.return_value = 0

        area = UploadArea(area_uuid)
        area.delete()

        record = UploadDB().get_pg_record("upload_area", area_uuid, column='uuid')
        self.assertEqual("DELETION_QUEUED", record["status"])

    def test_delete_with_unused_used_upload_area_uuid(self):
        area_uuid = str(uuid.uuid4())

        response = self.client.delete(f"/v1/area/{area_uuid}", headers=self.authentication_header)

        self.assertEqual(404, response.status_code)
        self.assertEqual('application/problem+json', response.content_type)

    def test_locking_of_upload_area(self):
        area_uuid = self._create_area()
        record = UploadDB().get_pg_record("upload_area", area_uuid, column='uuid')
        self.assertEqual("UNLOCKED", record["status"])

        response = self.client.post(f"/v1/area/{area_uuid}/lock", headers=self.authentication_header)

        self.assertEqual(204, response.status_code)
        record = UploadDB().get_pg_record("upload_area", area_uuid, column='uuid')
        self.assertEqual("LOCKED", record["status"])

        response = self.client.delete(f"/v1/area/{area_uuid}/lock", headers=self.authentication_header)

        self.assertEqual(204, response.status_code)
        record = UploadDB().get_pg_record("upload_area", area_uuid, column='uuid')
        self.assertEqual("UNLOCKED", record["status"])

    def test_put_file_without_content_type_dcp_type_param(self):
        headers = {'Content-Type': 'application/json'}
        headers.update(self.authentication_header)
        area_uuid = self._create_area()

        response = self.client.put(f"/v1/area/{area_uuid}/some.json", data="exquisite corpse", headers=headers)

        self.assertEqual(400, response.status_code)
        self.assertEqual('application/problem+json', response.content_type)
        self.assertIn("missing parameter \'dcp-type\'", response.data.decode('utf8'))

    def test_put_file(self):
        headers = {'Content-Type': 'application/json; dcp-type="metadata/sample"'}
        headers.update(self.authentication_header)
        area_uuid = self._create_area()

        response = self.client.put(f"/v1/area/{area_uuid}/some.json", data="exquisite corpse", headers=headers)

        self.assertEqual(201, response.status_code)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(f"s3://{self.upload_config.bucket_name}/{area_uuid}/some.json",
                         json.loads(response.data)['url'])

    def test_list_files(self):
        area_uuid = self._create_area()
        self.mock_upload_file_to_s3(area_uuid, 'file1')
        self.mock_upload_file_to_s3(area_uuid, 'file2')

        response = self.client.get(f"/v1/area/{area_uuid}")

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(json.loads(response.data)['files']))

    def test_get_file_for_existing_file(self):
        area_uuid = self._create_area()
        filename = 'file1.json'
        s3obj = self.mock_upload_file_to_s3(area_uuid, filename)

        response = self.client.get(f"/v1/area/{area_uuid}/{filename}")

        self.assertEqual(200, response.status_code)
        data = json.loads(response.data)
        self.assertIn('size', data.keys())  # moto file sizes are not accurate
        del data['size']
        self.assertEqual(data, {
            'upload_area_id': area_uuid,
            'name': 'file1.json',
            'last_modified': s3obj.last_modified.isoformat(),
            'content_type': 'application/json',
            'url': f"s3://{self.upload_config.bucket_name}/{area_uuid}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })

    def test_get_file_returns_404_for_missing_area_or_file(self):
        response = self.client.get(f"/v1/area/bogoarea/bogofile")
        self.assertEqual(404, response.status_code)

        area_uuid = str(uuid.uuid4())

        self.client.post(f"/v1/area/{area_uuid}", headers=self.authentication_header)

        response = self.client.get(f"/v1/area/{area_uuid}/bogofile")
        self.assertEqual(404, response.status_code)

    def test_put_files_info(self):
        area_uuid = self._create_area()
        o1 = self.mock_upload_file_to_s3(area_uuid, 'file1.json',
                                         content_type='application/json; dcp-type="metadata/foo"')
        o2 = self.mock_upload_file_to_s3(area_uuid, 'file2.fastq.gz',
                                         content_type='application/octet-stream; dcp-type=data',
                                         checksums={'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'})
        self.mock_upload_file_to_s3(area_uuid, 'a_file_in_the_same_area_that_we_will_not_attempt_to_list')

        response = self.client.put(f"/v1/area/{area_uuid}/files_info", content_type='application/json',
                                   data=(json.dumps(['file1.json', 'file2.fastq.gz'])))

        self.assertEqual(200, response.status_code)
        data = json.loads(response.data)
        self.assertEqual(2, len(data))

        self.assertIn('size', data[0].keys())  # moto file sizes are not accurate
        for fileinfo in data:
            del fileinfo['size']

        self.assertEqual(data[0], {
            'upload_area_id': area_uuid,
            'name': 'file1.json',
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/foo"',
            'url': f"s3://{self.upload_config.bucket_name}/{area_uuid}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        self.assertEqual(data[1], {
            'upload_area_id': area_uuid,
            'name': 'file2.fastq.gz',
            'last_modified': o2.last_modified.isoformat(),
            'content_type': 'application/octet-stream; dcp-type=data',
            'url': f"s3://{self.upload_config.bucket_name}/{area_uuid}/file2.fastq.gz",
            'checksums': {'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'}
        })

    def test_post_file_with_valid_area(self):
        area_uuid = self._create_area()

        response = self.client.post(f"/v1/area/{area_uuid}/filename123")
        message = self.sqs.meta.client.receive_message(QueueUrl='bogo_url')

        message_body = json.loads(message['Messages'][0]['Body'])
        s3_key = message_body['Records'][0]['s3']['object']['key']
        s3_bucket = message_body['Records'][0]['s3']['bucket']['name']
        self.assertEqual(202, response.status_code)
        self.assertEqual(s3_key, f"{area_uuid}/filename123")
        self.assertEqual(s3_bucket, "bogobucket")

    def test_post_file_with_invalid_area(self):
        area_uuid = str(uuid.uuid4())
        response = self.client.post(f"/v1/area/{area_uuid}/filename123")
        self.assertEqual(404, response.status_code)

    def test_add_uploaded_file_to_csum_daemon_sqs(self):
        area_uuid = self._create_area()

        UploadArea(area_uuid).add_uploaded_file_to_csum_daemon_sqs("filename123")
        message = self.sqs.meta.client.receive_message(QueueUrl='bogo_url')

        message_body = json.loads(message['Messages'][0]['Body'])
        s3_key = message_body['Records'][0]['s3']['object']['key']
        s3_bucket = message_body['Records'][0]['s3']['bucket']['name']
        self.assertEqual(s3_key, f"{area_uuid}/filename123")
        self.assertEqual(s3_bucket, "bogobucket")

    def test_add_upload_area_to_delete_sqs(self):
        area_uuid = self._create_area()

        UploadArea(area_uuid).add_upload_area_to_delete_sqs()
        message = self.sqs.meta.client.receive_message(QueueUrl='delete_sqs_url')

        message_body = json.loads(message['Messages'][0]['Body'])
        self.assertEqual(message_body['area_uuid'], area_uuid)
        record = UploadDB().get_pg_record("upload_area", area_uuid, column='uuid')
        self.assertEqual(record['status'], "DELETION_QUEUED")


if __name__ == '__main__':
    unittest.main()
