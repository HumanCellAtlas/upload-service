from .. import UploadTestCaseUsingLiveAWS, EnvironmentSetup, fixture_file_path

from upload.common.aws_secret import AwsSecret
from upload.common.upload_config import UploadConfig


class TestConfig(UploadTestCaseUsingLiveAWS):

    def setUp(self):
        super().setUp()
        self.aws_secret = AwsSecret(name="dcp/upload/bogo-env/secrets")
        self.aws_secret.update('{"secret1":"cloud_value1"}')

    def tearDown(self):
        self.aws_secret.delete()

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
