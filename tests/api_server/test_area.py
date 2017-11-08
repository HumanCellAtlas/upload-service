#!/usr/bin/env python3.6

import os, sys, unittest, uuid, json, base64

import boto3
from botocore.exceptions import ClientError
from moto import mock_s3, mock_iam

from . import client_for_test_api_server
from .. import EnvironmentSetup

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa


class TestApiAuthenticationErrors(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Setup app
        with EnvironmentSetup({
            'BUCKET_NAME_PREFIX': "bogobucket-",
            'DEPLOYMENT_STAGE': 'test',
            'INGEST_API_KEY': 'unguessable'
        }):
            self.client = client_for_test_api_server()

    def test_call_without_auth_setup(self):
        # Use a different app instance started without an INGEST_API_KEY
        with EnvironmentSetup({
            'BUCKET_NAME_PREFIX': "bogobucket-",
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


class TestAreaApi(unittest.TestCase):

    def setUp(self):
        # Setup mock AWS
        self.s3_mock = mock_s3()
        self.s3_mock.start()
        self.iam_mock = mock_iam()
        self.iam_mock.start()
        # Setup upload bucket
        self.deployment_stage = 'test'
        self.upload_bucket_name = f'bogobucket-{self.deployment_stage}'
        self.upload_bucket = boto3.resource('s3').Bucket(self.upload_bucket_name)
        self.upload_bucket.create()
        # Setup authentication
        self.api_key = "foo"
        os.environ['INGEST_API_KEY'] = self.api_key
        self.authentication_header = {'Api-Key': self.api_key}
        # Setup app
        with EnvironmentSetup({
            'DEPLOYMENT_STAGE': self.deployment_stage
        }):
            self.client = client_for_test_api_server()

    def tearDown(self):
        self.s3_mock.stop()
        self.iam_mock.stop()

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

    def test_create_in_production_returns_5_part_urn(self):
        with EnvironmentSetup({'DEPLOYMENT_STAGE': 'prod'}):

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

    def test_locking_of_upload_area(self):
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)
        user_name = f"upload-{self.deployment_stage}-user-" + area_id
        policy_name = 'upload-' + area_id
        policy = boto3.resource('iam').UserPolicy(user_name, policy_name)
        self.assertIn('{"Effect": "Allow", "Action": ["s3:PutObject"', policy.policy_document)

        response = self.client.post(f"/v1/area/{area_id}/lock", headers=self.authentication_header)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(list(boto3.resource('iam').User(user_name).policies.all())), 0)

        response = self.client.delete(f"/v1/area/{area_id}/lock", headers=self.authentication_header)

        self.assertEqual(response.status_code, 204)
        policy = boto3.resource('iam').UserPolicy(user_name, policy_name)
        self.assertIn('{"Effect": "Allow", "Action": ["s3:PutObject"', policy.policy_document)

    def test_put_file_without_content_type_dcp_type_param(self):
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)
        headers = {'Content-Type': 'application/json'}
        headers.update(self.authentication_header)

        response = self.client.put(f"/v1/area/{area_id}/some.json", data="exquisite corpse", headers=headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content_type, 'application/problem+json')
        self.assertIn("missing parameter \'dcp-type\'", response.data.decode('utf8'))

    def test_put_file(self):
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)
        headers = {'Content-Type': 'application/json; dcp-type="metadata/sample"'}
        headers.update(self.authentication_header)

        response = self.client.put(f"/v1/area/{area_id}/some.json", data="exquisite corpse", headers=headers)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(json.loads(response.data), {
            'upload_area_id': area_id,
            'name': 'some.json',
            'size': 16,
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

    def test_list_files(self):
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)
        file1_key = f"{area_id}/file1.json"
        self.upload_bucket.Object(file1_key).put(Body="foo", ContentType="application/json")
        boto3.client('s3').put_object_tagging(Bucket=self.upload_bucket_name, Key=file1_key, Tagging={
            'TagSet': [
                {'Key': 'hca-dss-content-type', 'Value': 'application/json'},
                {'Key': 'hca-dss-s3_etag', 'Value': '1'},
                {'Key': 'hca-dss-sha1', 'Value': '2'},
                {'Key': 'hca-dss-sha256', 'Value': '3'},
                {'Key': 'hca-dss-crc32c', 'Value': '4'}
            ]
        })
        file2_key = f"{area_id}/file2.json"
        self.upload_bucket.Object(file2_key).put(Body="ba ba ba ba ba barane", ContentType="dcp/data-file")
        boto3.client('s3').put_object_tagging(Bucket=self.upload_bucket_name, Key=file2_key, Tagging={
            'TagSet': [
                {'Key': 'hca-dss-content-type', 'Value': 'dcp/data-file'},
                {'Key': 'hca-dss-s3_etag', 'Value': 'a'},
                {'Key': 'hca-dss-sha1', 'Value': 'b'},
                {'Key': 'hca-dss-sha256', 'Value': 'c'},
                {'Key': 'hca-dss-crc32c', 'Value': 'd'}
            ]
        })

        response = self.client.get(f"/v1/area/{area_id}")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('size', data['files'][0].keys())  # moto file sizes are not accurate
        for fileinfo in data['files']:
            del fileinfo['size']
        self.assertEqual(data['files'][0], {
            'upload_area_id': area_id,
            'name': 'file1.json',
            'content_type': 'application/json',
            'url': f"s3://{self.upload_bucket_name}/{area_id}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        self.assertEqual(data['files'][1], {
            'upload_area_id': area_id,
            'name': 'file2.json',
            'content_type': 'dcp/data-file',
            'url': f"s3://{self.upload_bucket_name}/{area_id}/file2.json",
            'checksums': {'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'}
        })

    def test_list_files_only_lists_files_in_my_upload_area(self):
        area1_id = str(uuid.uuid4())
        area2_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area1_id}", headers=self.authentication_header)
        self.client.post(f"/v1/area/{area2_id}", headers=self.authentication_header)
        area_1_files = ['file1', 'file2']
        area_2_files = ['file3', 'file4']
        [self.upload_bucket.Object(f"{area1_id}/{file}").put(Body="foo") for file in area_1_files]
        [self.upload_bucket.Object(f"{area2_id}/{file}").put(Body="foo") for file in area_2_files]

        response = self.client.get(f"/v1/area/{area2_id}")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual([file['name'] for file in data['files']], area_2_files)


if __name__ == '__main__':
    unittest.main()
