import logging
import os
import unittest

import boto3
from moto import mock_iam, mock_s3, mock_sts, mock_sqs

from upload.common.upload_config import UploadConfig, UploadDbConfig, UploadVersion

os.environ['LOG_LEVEL'] = 'CRITICAL'
# logging.basicConfig(level=logging.DEBUG)
# logging.getLogger('botocore').setLevel(logging.WARNING)
# logging.getLogger('boto3').setLevel(logging.WARNING)


class EnvironmentSetup:
    """
    Set environment variables.
    Provide a dict of variable names and values.
    Setting a value to None will delete it from the environment.
    Works as a context manager:

        with EnvironmentSetup({'FOO': 'bar'}):
            pass

    or use enter() and exit()  (e.g. in setUp() and tearDown() functions).

        self.enver = EnvironmentSetup({'FOO': 'bar'})
        self.enver.enter()
        # Stuff
        self.enver.exit()
    """
    def __init__(self, env_vars_dict):
        self.env_vars = env_vars_dict
        self.saved_vars = {}
        self.logger = logging.getLogger('EnvironmentSetup')

    def enter(self):
        for k, v in self.env_vars.items():
            if k in os.environ:
                old_value = os.environ[k]
                self.saved_vars[k] = os.environ[k]
            else:
                old_value = None
            if v:
                os.environ[k] = v
                self.logger.debug(f"temporarily changing {k} from {old_value} to {v}")
            else:
                if k in os.environ:
                    del os.environ[k]
                    self.logger.debug(f"temporarily deleting {k}")

    def exit(self):
        for k, v in self.saved_vars.items():
            self.logger.debug(f"resetting {k} back to {v}")
            os.environ[k] = v

    def __enter__(self):
        self.enter()

    def __exit__(self, type, value, traceback):
        self.exit()


class UploadTestCase(unittest.TestCase):

    BOGO_CONFIG = {
        'bucket_name': 'bogobucket',
        'csum_job_q_arn': 'bogo_arn',
        'csum_upload_q_url': 'bogo_url',
        'area_deletion_q_url': 'delete_sqs_url',
        'csum_job_role_arn': 'bogo_role_arn',
        'upload_submitter_role_arn': 'bogo_submitter_role_arn',
        'slack_webhook': 'bogo_slack_url',
        'area_deletion_lambda_name': 'delete_lambda_name'
    }

    def setUp(self):
        # Common Environment
        if os.environ['DEPLOYMENT_STAGE'] in ['local', 'test']:
            self.deployment_stage = os.environ['DEPLOYMENT_STAGE']
        else:
            self.deployment_stage = 'test'
        self.environment = {
            'DEPLOYMENT_STAGE': self.deployment_stage
        }
        self.common_environmentor = EnvironmentSetup(self.environment)
        self.common_environmentor.enter()

        # UploadConfig
        self.upload_config = UploadConfig()
        self.upload_config.set(self.__class__.BOGO_CONFIG)

        # UploadVersion
        self.upload_version = UploadVersion()
        self.upload_version.set({"upload_service_version": "0"})

    def tearDown(self):
        self.common_environmentor.exit()


class UploadTestCaseUsingLiveAWS(UploadTestCase):

    def setUp(self):
        super().setUp()
        if self.deployment_stage == 'local':
            self.skipTest("requires Internet")

    def tearDown(self):
        super().tearDown()


class UploadTestCaseUsingMockAWS(UploadTestCase):

    def setUp(self):
        super().setUp()
        # Setup mock AWS
        self.s3_mock = mock_s3()
        self.s3_mock.start()
        self.iam_mock = mock_iam()
        self.iam_mock.start()
        self.sqs_mock = mock_sqs()
        self.sqs_mock.start()

        if self.deployment_stage == 'local':
            # When online, we need STS to access SecretsManager to access RDS.
            # When offline, mock out STS/SecretsManager and use local Postgres.
            # STS
            self.sts_mock = mock_sts()
            self.sts_mock.start()
            # UploadDbConfig
            self.upload_db_config = UploadDbConfig()
            self.upload_db_config.set({
                'database_uri': 'postgresql://:@localhost/upload_local',
                'pgbouncer_uri': 'postgresql://:@localhost/upload_local'
            })
        # Upload Bucket
        self.upload_bucket = boto3.resource('s3').Bucket(self.upload_config.bucket_name)
        self.upload_bucket.create()

        self.sqs = boto3.resource('sqs')
        self.sqs.create_queue(QueueName=f"bogo_url")
        self.sqs.create_queue(QueueName=f"delete_sqs_url")

    def tearDown(self):
        super().tearDown()
        self.s3_mock.stop()
        self.iam_mock.stop()
        if self.deployment_stage == 'local':
            self.sts_mock.stop()

    def create_s3_object(self, object_key, bucket_name=None,
                         content_type="application/octet-stream",
                         content="file_content"):
        bucket_name = bucket_name or self.upload_config.bucket_name
        s3 = boto3.resource('s3')
        s3object = s3.Bucket(bucket_name).Object(object_key)
        s3object.put(Body=content, ContentType=content_type)
        return s3object

    """
    Simulate a file that has been uploaded to the S3 upload bucket by the HCA CLI,
    and (optionally) checksummed by the Upload Service (provide checksums={} to disable).
    """
    def mock_upload_file_to_s3(self, area_id, filename, contents="foo", content_type="application/json",
                               checksums=None):
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
