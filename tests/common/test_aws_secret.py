import unittest

import boto3
from botocore.errorfactory import ClientError

from upload.common.aws_secret import AwsSecret

secrets_mgr = boto3.client("secretsmanager")


class TestAwsSecret(unittest.TestCase):

    UNKNOWN_SECRET = 'dcp/upload/test/secret_that_does_not_exist'  # Don't ever create this
    EXISTING_SECRET = 'dcp/upload/test/test_secret'
    EXISTING_SECRET_VALUE = '{"top":"secret"}'

    def setUp(self):
        # Create an active (non-deleted) secret.
        secret = None
        try:
            secret = secrets_mgr.describe_secret(SecretId=self.EXISTING_SECRET)
            self.secret_arn = secret['ARN']
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                raise e

        if not secret:
            secret = secrets_mgr.create_secret(Name=self.EXISTING_SECRET,
                                               SecretString=self.EXISTING_SECRET_VALUE)
            self.secret_arn = secret['ARN']
        else:
            if 'DeletedDate' in secret:
                secrets_mgr.restore_secret(SecretId=self.secret_arn)

            secrets_mgr.put_secret_value(SecretId=self.secret_arn,
                                         SecretString=self.EXISTING_SECRET_VALUE)

    def tearDown(self):
        secrets_mgr.delete_secret(SecretId=self.secret_arn)

    def test_init_of_unknown_secret_does_not_set_secret_metadata(self):
        secret = AwsSecret(name=self.UNKNOWN_SECRET)
        self.assertEqual(secret.secret_metadata, None)

    def test_init_of_existing_secret_retrieves_secret_metadata(self):
        secret = AwsSecret(name=self.EXISTING_SECRET)
        self.assertIsNotNone(secret.secret_metadata)

    # value

    def test_value_of_unknown_secret_raises_exception(self):
        secret = AwsSecret(name=self.UNKNOWN_SECRET)
        with self.assertRaisesRegex(RuntimeError, 'No such'):
            secret.value  # noqa

    def test_value_of_existing_deleted_secret_raises_exception(self):
        secret = AwsSecret(name=self.EXISTING_SECRET)
        secret.delete()
        with self.assertRaisesRegex(RuntimeError, 'deleted'):
            x =secret.value  # noqa

    def test_value_of_existing_secret_returns_value(self):
        secret = AwsSecret(name=self.EXISTING_SECRET)
        self.assertEqual(secret.value, self.EXISTING_SECRET_VALUE)

    # update

    # This is hard to test as AWS keeps secrets around after deletion.
    # If we ran this test twice, next time it would be unknown.
    # We could mint new secret names ever time, but that will pollute
    # the secret store with timing out secrets.
    #
    # def test_update_of_unknown_secret_creates_secret(self):
    #     secret = AwsSecret(name=self.UNKNOWN_SECRET)
    #     secret.update(value='{"foo":"bar"}')
    #     self.assertIsNotNone(secret.secret_metadata)

    def test_delete_of_unknown_secret_raises_exception(self):
        secret = AwsSecret(name=self.UNKNOWN_SECRET)
        with self.assertRaises(RuntimeError):
            secret.delete()

    def test_update_of_existing_secret_updates_secret(self):
        secret = AwsSecret(name=self.EXISTING_SECRET)
        secret.update(value='{"foo":"bar"}')
        self.assertEqual(secrets_mgr.get_secret_value(SecretId=self.secret_arn)['SecretString'],
                         '{"foo":"bar"}')

    # delete

    def test_delete_of_existing_secret_deletes_secret(self):
        secret = AwsSecret(name=self.EXISTING_SECRET)
        secret.delete()
        secret = secrets_mgr.describe_secret(SecretId=self.secret_arn)
        self.assertIn('DeletedDate', secret)
