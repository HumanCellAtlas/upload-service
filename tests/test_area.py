#!/usr/bin/env python3.6

import os, sys, unittest, uuid, json, base64

import boto3
from botocore.exceptions import ClientError
from moto import mock_s3, mock_iam
from connexion.lifecycle import ConnexionResponse

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from staging.api import area  # noqa


class TestArea(unittest.TestCase):

    @mock_s3
    @mock_iam
    def test_create_with_unused_staging_area_id(self):
        area_id = str(uuid.uuid4())

        response = area.create(area_id, 'aws')

        bucket_name = f"org-humancellatlas-staging-{area_id}"
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
            boto3.resource('s3').Bucket(bucket_name).load()
        except ClientError:
            self.fail("Bucket was not created!")

    @mock_s3
    @mock_iam
    def test_create_with_already_used_staging_area_id(self):
        area_id = str(uuid.uuid4())
        bucket_name = f"org-humancellatlas-staging-{area_id}"
        boto3.resource('s3').Bucket(bucket_name).create()

        response = area.create(area_id, 'aws')

        self.assertEqual(response.__class__, ConnexionResponse)
        self.assertEqual(response.content_type, 'application/problem+json')
        self.assertEqual(response.status_code, 409)

    @mock_s3
    @mock_iam
    def test_delete_with_id_of_real_non_empty_staging_area(self):
        area_id = str(uuid.uuid4())
        bucket = boto3.resource('s3').Bucket(f"org-humancellatlas-staging-{area_id}")
        bucket.create()
        bucket.Object('test_file').put(Body="foo")
        boto3.resource('iam').User(f"staging-user-{area_id}").create()

        response = area.delete(area_id, 'aws')

        body, status_code = response
        self.assertEqual(status_code, 204)

    @mock_s3
    @mock_iam
    def test_delete_with_unused_used_staging_area_id(self):
        area_id = str(uuid.uuid4())

        response = area.delete(area_id, 'aws')

        self.assertEqual(response.__class__, ConnexionResponse)
        self.assertEqual(response.content_type, 'application/problem+json')
        self.assertEqual(response.status_code, 404)

    @mock_s3
    @mock_iam
    def test_locking_of_staging_area(self):
        area_id = str(uuid.uuid4())
        area.create(area_id, 'aws')
        user_name = 'staging-user-' + area_id
        policy_name = 'staging-' + area_id
        policy = boto3.resource('iam').UserPolicy(user_name, policy_name)
        self.assertIn('{"Effect": "Allow", "Action": ["s3:ListBucket", "s3:PutObject"]', policy.policy_document)

        body, status_code = area.lock(area_id, 'aws')

        self.assertEqual(status_code, 200)
        policy = boto3.resource('iam').UserPolicy(user_name, policy_name)
        self.assertIn('{"Effect": "Allow", "Action": ["s3:ListBucket"]', policy.policy_document)

        body, status_code = area.unlock(area_id, 'aws')

        self.assertEqual(status_code, 200)
        policy = boto3.resource('iam').UserPolicy(user_name, policy_name)
        self.assertIn('{"Effect": "Allow", "Action": ["s3:ListBucket", "s3:PutObject"]', policy.policy_document)

    @mock_s3
    @mock_iam
    def test_put_file(self):
        area_id = str(uuid.uuid4())
        area.create(area_id, 'aws')

        area.put_file(staging_area_id=area_id, cloud='aws', filename="some.json", body="exquisite corpse")

        bucket = boto3.resource('s3').Bucket(f"org-humancellatlas-staging-{area_id}")
        obj = bucket.Object("some.json")
        self.assertEqual(obj.get()['Body'].read(), "exquisite corpse".encode('utf8'))

    @mock_s3
    @mock_iam
    def test_list_area(self):
        area_id = str(uuid.uuid4())
        bucket_name = f"org-humancellatlas-staging-{area_id}"
        bucket = boto3.resource('s3').Bucket(bucket_name)
        bucket.create()
        bucket.Object('file1.json').put(Body="foo")
        boto3.client('s3').put_object_tagging(Bucket=bucket_name, Key='file1.json', Tagging={
                'TagSet': [
                    {'Key': 'hca-dss-content-type', 'Value': 'application/json'},
                    {'Key': 'hca-dss-s3_etag', 'Value': '1'},
                    {'Key': 'hca-dss-sha1', 'Value': '2'},
                    {'Key': 'hca-dss-sha256', 'Value': '3'},
                    {'Key': 'hca-dss-crc32c', 'Value': '4'}
                ]
            }
        )
        file1_size = 364  # for some reason adding tags to a file increases its size when testing with moto
        bucket.Object('file2.json').put(Body="ba ba ba ba ba barane")
        boto3.client('s3').put_object_tagging(Bucket=bucket_name, Key='file2.json', Tagging={
                'TagSet': [
                    {'Key': 'hca-dss-content-type', 'Value': 'application/json'},
                    {'Key': 'hca-dss-s3_etag', 'Value': 'a'},
                    {'Key': 'hca-dss-sha1', 'Value': 'b'},
                    {'Key': 'hca-dss-sha256', 'Value': 'c'},
                    {'Key': 'hca-dss-crc32c', 'Value': 'd'}
                ]
            }
        )
        file2_size = 364  # for some reason adding tags to a file increases its size when testing with moto

        response, status_code = area.list_area(staging_area_id=area_id, cloud='aws')

        self.assertEqual(status_code, 200)
        self.assertEqual(response['files'][0]['name'], "file1.json")
        self.assertEqual(response['files'][0]['content-type'], 'application/json')
        self.assertEqual(response['files'][0]['size'], file1_size)
        self.assertEqual(response['files'][0]['s3_etag'], '1')
        self.assertEqual(response['files'][0]['sha1'], '2')
        self.assertEqual(response['files'][0]['sha256'], '3')
        self.assertEqual(response['files'][0]['crc32c'], '4')

        self.assertEqual(response['files'][1]['name'], "file2.json")
        self.assertEqual(response['files'][1]['content-type'], 'application/json')
        self.assertEqual(response['files'][1]['size'], file2_size)
        self.assertEqual(response['files'][1]['s3_etag'], 'a')
        self.assertEqual(response['files'][1]['sha1'], 'b')
        self.assertEqual(response['files'][1]['sha256'], 'c')
        self.assertEqual(response['files'][1]['crc32c'], 'd')

if __name__ == '__main__':
    unittest.main()
