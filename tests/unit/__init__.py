import os
import unittest

import boto3
from moto import mock_iam, mock_s3, mock_sts

from upload.common.upload_config import UploadConfig

os.environ['DEPLOYMENT_STAGE'] = 'test'
os.environ['LOG_LEVEL'] = 'CRITICAL'


class EnvironmentSetup:
    """
    Set environment variables.
    Provide a dict of variable names and values.
    Setting a value to None will delete it from the environment.
    """
    def __init__(self, env_vars_dict):
        self.env_vars = env_vars_dict
        self.saved_vars = {}

    def enter(self):
        for k, v in self.env_vars.items():
            if k in os.environ:
                self.saved_vars[k] = os.environ[k]
            if v:
                os.environ[k] = v
            else:
                if k in os.environ:
                    del os.environ[k]

    def exit(self):
        for k, v in self.saved_vars.items():
            os.environ[k] = v

    def __enter__(self):
        self.enter()

    def __exit__(self, type, value, traceback):
        self.exit()


class UploadTestCaseUsingLiveAWS(unittest.TestCase):

    def setUp(self):
        # Does nothing but provide for consistency in test subclasses.
        pass

    def tearDown(self):
        # Does nothing but provide for consistency in test subclasses.
        pass


class UploadTestCaseUsingMockAWS(unittest.TestCase):

    def setUp(self):
        # Setup mock AWS
        self.s3_mock = mock_s3()
        self.s3_mock.start()
        self.iam_mock = mock_iam()
        self.iam_mock.start()
        self.sts_mock = mock_sts()
        self.sts_mock.start()
        # UploadConfig
        self.upload_config = UploadConfig()
        self.upload_config.set({
            'bucket_name': 'bogobucket',
            'csum_job_q_arn': 'bogo_arn',
            'csum_job_role_arn': 'bogo_role_arn',
            'upload_submitter_role_arn': 'bogo_submitter_role_arn',
            'slack_webhook': 'bogo_slack_url'
        })
        # Common Environment
        self.deployment_stage = 'test'
        self.environment = {
            'DEPLOYMENT_STAGE': self.deployment_stage
        }
        self.common_environmentor = EnvironmentSetup(self.environment)
        self.common_environmentor.enter()
        # Upload Bucket
        self.upload_bucket = boto3.resource('s3').Bucket(self.upload_config.bucket_name)
        self.upload_bucket.create()

    def tearDown(self):
        self.s3_mock.stop()
        self.iam_mock.stop()
        self.sts_mock.stop()
        self.common_environmentor.exit()

    """
    Simulate a file that has been uploaded to the S3 upload bucket by the HCA CLI,
    and (optionally) checksummed by the Upload Service (provide checksums={} to disable).
    """
    def mock_upload_file(self, area_id, filename, contents="foo", content_type="application/json", checksums=None):
        if checksums is None:
            checksums = {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        file1_key = f"{area_id}/{filename}"
        s3obj = self.upload_bucket.Object(file1_key)
        s3obj.put(Body=contents, ContentType=content_type)
        tag_set = [{'Key': f"hca-dss-{csum_type}", 'Value': csum_value} for csum_type, csum_value in checksums.items()]
        if tag_set:
            boto3.client('s3').put_object_tagging(Bucket=self.upload_config.bucket_name,
                                                  Key=file1_key,
                                                  Tagging={'TagSet': tag_set})
        return s3obj
