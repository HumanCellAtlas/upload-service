from unittest.mock import PropertyMock, patch

from .. import UploadTestCaseUsingLiveAWS, EnvironmentSetup
from ... import fixture_file_path

from upload.common.aws_secret import AwsSecret
from upload.common.upload_config import UploadConfig


class TestConfig(UploadTestCaseUsingLiveAWS):

    def setUp(self):
        self.aws_secret = AwsSecret(name="dcp/upload/bogo-env/secrets")
        self.aws_secret.update('{"secret1":"secret1_from_cloud"}')
        UploadConfig.reset()
        super().setUp()

    def tearDown(self):
        self.aws_secret.delete()
        super().tearDown()

    def test_from_file(self):
        with EnvironmentSetup({
            'CONFIG_SOURCE': fixture_file_path('config.js')
        }):
            config = UploadConfig(deployment='bogo-env')
            self.assertEqual('value_from_file', config.secret1)

    def test_from_aws(self):
        with EnvironmentSetup({
            'CONFIG_SOURCE': None
        }):
            config = UploadConfig(deployment='bogo-env', source='aws')
            self.assertEqual('secret1_from_cloud', config.secret1)

    @patch('upload.common.upload_config.AwsSecret')
    def test_singletonness(self, mock_AwsSecret):
        value_mock = PropertyMock(return_value='{"secret2": "foo"}')
        type(mock_AwsSecret()).value = value_mock

        config1 = UploadConfig(deployment='bogo-env', source='aws')
        self.assertEqual('foo', config1.secret2)

        config2 = UploadConfig(deployment='bogo-env', source='aws')
        self.assertEqual('foo', config2.secret2)

        value_mock.assert_called_once()

    # TRUTH TABLE
    # ITEM IS IN CONFIG | ITEM IS IN ENV | use_env IS SET | RESULT
    #        no         |       no       |       no       | exception
    #        no         |       no       |       yes      | exception
    #        no         |       yes      |       no       | exception
    #        no         |       yes      |       yes      | return env value
    #        yes        |       no       |       no       | return config value
    #        yes        |       no       |       yes      | return config value
    #        yes        |       yes      |       no       | return config value
    #        yes        |       yes      |       no       | return config value
    #        yes        |       yes      |       yes      | return env value

    def test_when_item_is_not_in_config_not_in_env_we_raise(self):
        self.aws_secret.update('{}')
        with EnvironmentSetup({
            'CONFIG_SOURCE': None,
        }):
            with self.assertRaises(RuntimeError):
                config = UploadConfig(deployment='bogo-env')
                print(config.secret1)

    def test_when_item_is_not_in_config_but_is_in_env_and_use_env_is_not_set_we_raise(self):
        self.aws_secret.update('{}')
        with EnvironmentSetup({
            'CONFIG_SOURCE': None,
            'SECRET1': 'secret1_from_env'
        }):
            with self.assertRaises(RuntimeError):
                config = UploadConfig(deployment='bogo-env')
                print(config.secret1)

    def test_when_item_is_not_in_config_but_is_in_env_and_use_env_is_set_we_use_env(self):
        self.aws_secret.update('{}')
        UploadConfig.use_env = True
        with EnvironmentSetup({
            'CONFIG_SOURCE': None,
            'SECRET1': 'secret1_from_env'
        }):
            config = UploadConfig(deployment='bogo-env')
            self.assertEqual('secret1_from_env', config.secret1)

    def test_when_item_is_in_config_but_not_in_env_and_use_env_is_not_set_we_use_config(self):
        with EnvironmentSetup({
            'CONFIG_SOURCE': None,
        }):
            config = UploadConfig(deployment='bogo-env')
            self.assertEqual('secret1_from_cloud', config.secret1)

    def test_when_item_is_in_config_but_not_in_env_and_use_env_is_set_we_use_config(self):
        UploadConfig.use_env = True
        with EnvironmentSetup({
            'CONFIG_SOURCE': None,
            'SECRET1': 'secret1_from_env'
        }):
            config = UploadConfig(deployment='bogo-env')
            self.assertEqual('secret1_from_env', config.secret1)

    def test_when_item_is_in_config_and_is_in_env_and_use_env_is_set_we_use_env(self):
        UploadConfig.use_env = True
        with EnvironmentSetup({
            'CONFIG_SOURCE': None,
            'SECRET1': 'secret1_from_env'
        }):
            config = UploadConfig(deployment='bogo-env')
            self.assertEqual('secret1_from_env', config.secret1)
