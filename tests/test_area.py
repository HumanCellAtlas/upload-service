#!/usr/bin/env python3.6

import os, sys, unittest, uuid, json, base64, functools

import connexion
import boto3
from botocore.exceptions import ClientError
from moto import mock_s3, mock_iam

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa


class TestAreaWithoutAuthSetup(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Setup app
        flask_app = connexion.FlaskApp(__name__)
        flask_app.add_api('../config/staging-api.yml')
        self.client = flask_app.app.test_client()

    def test_create_raises_exception(self):
        response = self.client.post(f"/v1/area/{str(uuid.uuid4())}")

        self.assertEqual(response.status_code, 500)
        self.assertIn("INGEST_API_KEY", response.data.decode('utf8'))


class TestArea(unittest.TestCase):

    def setUp(self):
        # Setup mock AWS
        self.s3_mock = mock_s3()
        self.s3_mock.start()
        self.iam_mock = mock_iam()
        self.iam_mock.start()
        # Setup Staging bucket
        self.staging_bucket_name = os.environ['STAGING_S3_BUCKET']
        self.staging_bucket = boto3.resource('s3').Bucket(self.staging_bucket_name)
        self.staging_bucket.create()
        self.deployment_stage = os.environ['DEPLOYMENT_STAGE']
        # Setup authentication
        self.api_key = "foo"
        os.environ['INGEST_API_KEY'] = self.api_key
        self.authentication_header = {'Api-Key': self.api_key}
        # Setup app
        flask_app = connexion.FlaskApp(__name__)
        flask_app.add_api('../config/staging-api.yml')
        self.client = flask_app.app.test_client()

    def tearDown(self):
        self.s3_mock.stop()
        self.iam_mock.stop()
        del os.environ['INGEST_API_KEY']

    def test_create_while_unauthenticated(self):
        area_id = str(uuid.uuid4())

        response = self.client.post(f"/v1/area/{area_id}")

        self.assertEqual(response.status_code, 401)

    def test_create_with_unused_staging_area_id(self):
        area_id = str(uuid.uuid4())

        response = self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(response.status_code, 201)
        body = json.loads(response.data)
        self.assertEqual(list(body.keys()), ['urn'])
        urnbits = body['urn'].split(':')
        self.assertEqual(urnbits[0:3], ['hca', 'sta', 'aws'])
        self.assertEqual(urnbits[3], area_id)
        creds = json.loads(base64.b64decode(urnbits[4].encode('utf8')))
        self.assertEqual(list(creds.keys()), ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'])

        try:
            user_name = f"staging-{self.deployment_stage}-user-{area_id}"
            user = boto3.resource('iam').User(user_name)
            user.load()
        except ClientError:
            self.fail("Staging area (user) was not created!")
        policy = user.Policy(f"staging-{area_id}")
        self.assertIn('{"Effect": "Allow", "Action": ["s3:PutObject"', policy.policy_document)
        self.assertIn(f'"Resource": ["arn:aws:s3:::{self.staging_bucket_name}/{area_id}/*"]',
                      policy.policy_document)

    def test_create_with_already_used_staging_area_id(self):
        area_id = str(uuid.uuid4())
        user_name = f"staging-{self.deployment_stage}-user-{area_id}"
        boto3.resource('iam').User(user_name).create()

        response = self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.content_type, 'application/problem+json')

    def test_delete_with_id_of_real_non_empty_staging_area(self):
        area_id = str(uuid.uuid4())
        user = boto3.resource('iam').User(f"staging-{self.deployment_stage}-user-{area_id}")
        user.create()
        bucket = boto3.resource('s3').Bucket(self.staging_bucket_name)
        bucket.create()
        obj = bucket.Object(f'{area_id}/test_file')
        obj.put(Body="foo")

        response = self.client.delete(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(response.status_code, 204)
        with self.assertRaises(ClientError):
            user.load()
        with self.assertRaises(ClientError):
            obj.load()

    def test_delete_with_unused_used_staging_area_id(self):
        area_id = str(uuid.uuid4())

        response = self.client.delete(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content_type, 'application/problem+json')

    def test_locking_of_staging_area(self):
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)
        user_name = f"staging-{self.deployment_stage}-user-" + area_id
        policy_name = 'staging-' + area_id
        policy = boto3.resource('iam').UserPolicy(user_name, policy_name)
        self.assertIn('{"Effect": "Allow", "Action": ["s3:PutObject"', policy.policy_document)

        response = self.client.post(f"/v1/area/{area_id}/lock", headers=self.authentication_header)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(list(boto3.resource('iam').User(user_name).policies.all())), 0)

        response = self.client.delete(f"/v1/area/{area_id}/lock", headers=self.authentication_header)

        self.assertEqual(response.status_code, 204)
        policy = boto3.resource('iam').UserPolicy(user_name, policy_name)
        self.assertIn('{"Effect": "Allow", "Action": ["s3:PutObject"', policy.policy_document)

    def test_put_file(self):
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        response = self.client.put(f"/v1/area/{area_id}/some.json", data="exquisite corpse",
                                   headers=self.authentication_header)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(json.loads(response.data), {
            'staging_area_id': area_id,
            'name': 'some.json',
            'size': 16,
            'content_type': 'unknown',  # TODO
            'url': f"s3://{self.staging_bucket_name}/{area_id}/some.json",
            'checksums': {
                "crc32c": "FE9ADA52",
                "s3_etag": "18f17fbfdd21cf869d664731e10d4ffd",
                "sha1": "b1b101e21cf9cf8a4729da44d7818f935eec0ce8",
                "sha256": "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70"
            }
        })
        obj = self.staging_bucket.Object(f"{area_id}/some.json")
        self.assertEqual(obj.get()['Body'].read(), "exquisite corpse".encode('utf8'))

    def test_list_files(self):
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)
        file1_key = f"{area_id}/file1.json"
        self.staging_bucket.Object(file1_key).put(Body="foo")
        boto3.client('s3').put_object_tagging(Bucket=self.staging_bucket_name, Key=file1_key, Tagging={
            'TagSet': [
                {'Key': 'hca-dss-content-type', 'Value': 'application/json'},
                {'Key': 'hca-dss-s3_etag', 'Value': '1'},
                {'Key': 'hca-dss-sha1', 'Value': '2'},
                {'Key': 'hca-dss-sha256', 'Value': '3'},
                {'Key': 'hca-dss-crc32c', 'Value': '4'}
            ]
        })
        file2_key = f"{area_id}/file2.json"
        self.staging_bucket.Object(file2_key).put(Body="ba ba ba ba ba barane")
        boto3.client('s3').put_object_tagging(Bucket=self.staging_bucket_name, Key=file2_key, Tagging={
            'TagSet': [
                {'Key': 'hca-dss-content-type', 'Value': 'application/json'},
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
            'staging_area_id': area_id,
            'name': 'file1.json',
            'content_type': 'application/json',
            'url': f"s3://{self.staging_bucket_name}/{area_id}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        self.assertEqual(data['files'][1], {
            'staging_area_id': area_id,
            'name': 'file2.json',
            'content_type': 'application/json',
            'url': f"s3://{self.staging_bucket_name}/{area_id}/file2.json",
            'checksums': {'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'}
        })

    def test_list_files_only_lists_files_in_my_staging_area(self):
        area1_id = str(uuid.uuid4())
        area2_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area1_id}", headers=self.authentication_header)
        self.client.post(f"/v1/area/{area2_id}", headers=self.authentication_header)
        area_1_files = ['file1', 'file2']
        area_2_files = ['file3', 'file4']
        [self.staging_bucket.Object(f"{area1_id}/{file}").put(Body="foo") for file in area_1_files]
        [self.staging_bucket.Object(f"{area2_id}/{file}").put(Body="foo") for file in area_2_files]

        response = self.client.get(f"/v1/area/{area2_id}")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual([file['name'] for file in data['files']], area_2_files)

if __name__ == '__main__':
    unittest.main()
