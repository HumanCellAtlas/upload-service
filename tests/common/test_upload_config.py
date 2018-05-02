from .. import UploadTestCaseUsingLiveAWS, EnvironmentSetup, fixture_file_path

from upload.common.aws_secret import AwsSecret
from upload.common.upload_config import UploadConfig


class TestConfig(UploadTestCaseUsingLiveAWS):

    def setUp(self):
        super().setUp()
        self.config = AwsSecret(name="dcp/upload/test/secrets")
        self.config.update('{"a_secret":"value_from_cloud"}')
        UploadConfig.reset()

    def tearDown(self):
        self.config.delete()

    def test_environment_variables_override_other_sources(self):
        with EnvironmentSetup({
            'A_SECRET': 'value_from_env'
        }):
            config = UploadConfig(deployment='test')
            self.assertEqual(config.a_secret, 'value_from_env')

    def test_from_file(self):
        with EnvironmentSetup({
            'A_SECRET': None,
            'CONFIG_SOURCE': fixture_file_path('config.js')
        }):
            config = UploadConfig(deployment='test')
            self.assertEqual(config.a_secret, 'value_from_file')

    def test_from_aws(self):
        with EnvironmentSetup({
            'A_SECRET': None
        }):
            config = UploadConfig(deployment='test', source='aws')
            self.assertEqual(config.a_secret, 'value_from_cloud')
