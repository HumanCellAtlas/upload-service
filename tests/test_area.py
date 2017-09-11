#!/usr/bin/env python3.6

import os, sys, unittest, uuid, json, base64, functools

import boto3
from botocore.exceptions import ClientError
from moto import mock_s3, mock_iam
from connexion.lifecycle import ConnexionResponse

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from staging.api import area  # noqa


class TestArea(unittest.TestCase):

    def setUp(self):
        self.s3_mock = mock_s3()
        self.s3_mock.start()
        self.iam_mock = mock_iam()
        self.iam_mock.start()
        self.staging_bucket_name = os.environ['STAGING_S3_BUCKET']
        self.staging_bucket = boto3.resource('s3').Bucket(self.staging_bucket_name)
        self.staging_bucket.create()
        self.deployment_stage = os.environ['DEPLOYMENT_STAGE']

    def tearDown(self):
        self.s3_mock.stop()
        self.iam_mock.stop()

    def test_create_with_unused_staging_area_id(self):
        area_id = str(uuid.uuid4())

        response = area.create(area_id)

        self.assertEqual(response.__class__, tuple)
        self.assertEqual(len(response), 2)
        body, status_code = response
        self.assertEqual(status_code, 201)
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
        self.assertIn('{"Effect": "Allow", "Action": ["s3:PutObject"]', policy.policy_document)
        self.assertIn(f'"Resource": ["arn:aws:s3:::{self.staging_bucket_name}/{area_id}/*"]',
                      policy.policy_document)

    def test_create_with_already_used_staging_area_id(self):
        area_id = str(uuid.uuid4())
        user_name = f"staging-{self.deployment_stage}-user-{area_id}"
        boto3.resource('iam').User(user_name).create()

        response = area.create(area_id)

        self.assertEqual(response.__class__, ConnexionResponse)
        self.assertEqual(response.content_type, 'application/problem+json')
        self.assertEqual(response.status_code, 409)

    def test_delete_with_id_of_real_non_empty_staging_area(self):
        area_id = str(uuid.uuid4())
        user = boto3.resource('iam').User(f"staging-{self.deployment_stage}-user-{area_id}")
        user.create()
        bucket = boto3.resource('s3').Bucket(self.staging_bucket_name)
        bucket.create()
        obj = bucket.Object(f'{area_id}/test_file')
        obj.put(Body="foo")

        response = area.delete(area_id)

        body, status_code = response
        self.assertEqual(status_code, 204)
        with self.assertRaises(ClientError):
            user.load()
        with self.assertRaises(ClientError):
            obj.load()

    def test_delete_with_unused_used_staging_area_id(self):
        area_id = str(uuid.uuid4())

        response = area.delete(area_id)

        self.assertEqual(response.__class__, ConnexionResponse)
        self.assertEqual(response.content_type, 'application/problem+json')
        self.assertEqual(response.status_code, 404)

    def test_locking_of_staging_area(self):
        area_id = str(uuid.uuid4())
        area.create(area_id)
        user_name = f"staging-{self.deployment_stage}-user-" + area_id
        policy_name = 'staging-' + area_id
        policy = boto3.resource('iam').UserPolicy(user_name, policy_name)
        self.assertIn('{"Effect": "Allow", "Action": ["s3:PutObject"]', policy.policy_document)

        body, status_code = area.lock(area_id)

        self.assertEqual(status_code, 200)
        self.assertEqual(len(list(boto3.resource('iam').User(user_name).policies.all())), 0)

        body, status_code = area.unlock(area_id)

        self.assertEqual(status_code, 200)
        policy = boto3.resource('iam').UserPolicy(user_name, policy_name)
        self.assertIn('{"Effect": "Allow", "Action": ["s3:PutObject"]', policy.policy_document)

    def test_put_file(self):
        area_id = str(uuid.uuid4())
        area.create(area_id)

        response, status_code = area.put_file(staging_area_id=area_id, filename="some.json", body="exquisite corpse")

        self.assertEqual(status_code, 200)
        self.assertEqual(response, { 'url': f"s3://{self.staging_bucket_name}/{area_id}/some.json"})
        obj = self.staging_bucket.Object(f"{area_id}/some.json")
        self.assertEqual(obj.get()['Body'].read(), "exquisite corpse".encode('utf8'))

    def test_list_files(self):
        area_id = str(uuid.uuid4())
        area.create(area_id)
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

        response, status_code = area.list_files(staging_area_id=area_id)

        self.assertEqual(status_code, 200)
        self.assertEqual(response['files'][0]['name'], "file1.json")
        self.assertEqual(response['files'][0]['content_type'], 'application/json')
        self.assertIn('size', response['files'][0].keys())  # moto file sizes are not accurate
        self.assertEqual(response['files'][0]['checksums'], {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'})

        self.assertEqual(response['files'][1]['name'], "file2.json")
        self.assertEqual(response['files'][1]['content_type'], 'application/json')
        self.assertIn('size', response['files'][1].keys())  # moto file sizes are not accurate
        self.assertEqual(response['files'][1]['checksums'], {'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'})

    def test_list_files_only_lists_files_in_my_staging_area(self):
        area1_id = str(uuid.uuid4())
        area2_id = str(uuid.uuid4())
        area.create(area1_id)
        area.create(area2_id)
        area_1_files = ['file1', 'file2']
        area_2_files = ['file3', 'file4']
        [self.staging_bucket.Object(f"{area1_id}/{file}").put(Body="foo") for file in area_1_files]
        [self.staging_bucket.Object(f"{area2_id}/{file}").put(Body="foo") for file in area_2_files]

        response, status_code = area.list_files(staging_area_id=area2_id)

        self.assertEqual([file['name'] for file in response['files']], area_2_files)

if __name__ == '__main__':
    unittest.main()
