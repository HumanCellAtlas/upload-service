from .. import UploadTestCaseUsingLiveAWS, EnvironmentSetup, fixture_file_path

from upload.common.aws_secret import AwsSecret
from upload.common.upload_config import UploadConfig


class TestConfig(UploadTestCaseUsingLiveAWS):

    def setUp(self):
        super().setUp()
        self.aws_secret1 = AwsSecret(name="dcp/upload/bogo-env/secrets")
        self.aws_secret1.update('{"secret1":"cloud_value1"}')
        self.aws_secret2 = AwsSecret(name="dcp/upload/bogo-env/secrets2")
        self.aws_secret2.update('{"secret2":"cloud_value2"}')

    def tearDown(self):
        self.aws_secret1.delete()
        self.aws_secret2.delete()

    def test_environment_variables_override_other_sources(self):
        with EnvironmentSetup({
            'SECRET1': 'value_from_env',
            'CONFIG_SOURCE': None
        }):
            config = UploadConfig(deployment='bogo-env')
            self.assertEqual(config.secret1, 'value_from_env')

    def test_from_file(self):
        with EnvironmentSetup({
            'SECRET1': None,
            'CONFIG_SOURCE': fixture_file_path('config.js')
        }):
            config = UploadConfig(deployment='bogo-env')
            self.assertEqual(config.secret1, 'value_from_file')

    def test_from_aws(self):
        with EnvironmentSetup({
            'SECRET1': None,
            'CONFIG_SOURCE': None
        }):
            config = UploadConfig(deployment='bogo-env', source='aws')
            self.assertEqual(config.secret1, 'cloud_value1')

    def test_it_keeps_multiple_secrets_separate(self):
        with EnvironmentSetup({
            'SECRET1': None,
            'CONFIG_SOURCE': None
        }):
            config1 = UploadConfig(deployment='bogo-env')
            self.assertEqual(config1.secret1, 'cloud_value1')

            config2 = UploadConfig(deployment='bogo-env', secret='secrets2')
            self.assertEqual(config2.secret2, 'cloud_value2')

            self.assertEqual(config1.secret1, 'cloud_value1')
