import os, sys, unittest, json

import connexion

from .. import EnvironmentSetup

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa


class TestConfigApi(unittest.TestCase):

    def setUp(self):
        with EnvironmentSetup({'BUCKET_NAME_PREFIX': 'bogobucket-',
                               'DEPLOYMENT_STAGE': 'test'}):
            flask_app = connexion.FlaskApp(__name__)
            flask_app.add_api('../../config/upload-api.yml')
            self.client = flask_app.app.test_client()

    def test_client_config(self):

        with EnvironmentSetup({'BUCKET_NAME_PREFIX': 'bogo-prefix-',
                               'DEPLOYMENT_STAGE': 'test'}):

            response = self.client.get("/v1/config/client")

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data, {
                'upload_bucket_template': 'bogo-prefix-{deployment_stage}'
            })
