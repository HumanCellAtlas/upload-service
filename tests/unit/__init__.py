import os
import unittest

from moto import mock_iam, mock_s3, mock_sts

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

    def tearDown(self):
        self.s3_mock.stop()
        self.iam_mock.stop()
        self.sts_mock.stop()
