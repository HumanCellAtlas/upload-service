import os, sys, unittest, json

from . import client_for_test_api_server
from ... import EnvironmentSetup

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa


class TestConfigApi(unittest.TestCase):

    def setUp(self):
        self.client = client_for_test_api_server()

    def test_client_config(self):

        with EnvironmentSetup({'BUCKET_NAME_TEMPLATE': 'bogo-prefix-{deployment_stage}',
                               'DEPLOYMENT_STAGE': 'test'}):

            response = self.client.get("/v1/config/client")

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data, {
                'upload_bucket_template': 'bogo-prefix-{deployment_stage}'
            })
