#!/usr/bin/env python3.6

import os, sys, unittest, uuid

import boto3
from botocore.exceptions import ClientError
from moto import mock_s3
from connexion.lifecycle import ConnexionResponse

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from staging.api import area


class TestArea(unittest.TestCase):

    @mock_s3
    def test_create_with_unused_staging_area_id(self):
        area_id = uuid.uuid4()
        response = area.create(area_id)

        bucket_name = f"org-humancellatlas-staging-{area_id}"
        self.assertEqual(response.__class__, tuple)
        self.assertEqual(len(response), 2)
        body, status_code = response
        self.assertEqual(body, {'url': f"s3://{bucket_name}"})
        self.assertEqual(status_code, 201)

        try:
            boto3.resource('s3').Bucket(bucket_name).load()
        except ClientError:
            self.fail("Bucket was not created!")

    @mock_s3
    def test_create_with_already_used_staging_area_id(self):
        area_id = uuid.uuid4()
        bucket_name = f"org-humancellatlas-staging-{area_id}"
        boto3.resource('s3').Bucket(bucket_name).create()

        response = area.create(area_id)

        self.assertEqual(response.__class__, ConnexionResponse)
        self.assertEqual(response.content_type, 'application/problem+json')
        self.assertEqual(response.status_code, 409)

    @mock_s3
    def test_delete_with_id_of_real_staging_area(self):
        area_id = uuid.uuid4()
        bucket_name = f"org-humancellatlas-staging-{area_id}"
        boto3.resource('s3').Bucket(bucket_name).create()

        response = area.delete(area_id)

        body, status_code = response
        self.assertEqual(status_code, 204)

    @mock_s3
    def test_delete_with_unused_used_staging_area_id(self):
        area_id = uuid.uuid4()

        response = area.delete(area_id)

        self.assertEqual(response.__class__, ConnexionResponse)
        self.assertEqual(response.content_type, 'application/problem+json')
        self.assertEqual(response.status_code, 404)

if __name__ == '__main__':
    unittest.main()
