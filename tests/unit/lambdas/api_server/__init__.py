import os
import yaml

import connexion


api_server_client = None


def client_for_test_api_server():
    global api_server_client

    if not api_server_client:
        flask_app = connexion.FlaskApp(__name__)

        swagger_yaml_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                         '../../../../config/upload-api.yml'))
        with open(swagger_yaml_path, mode='rb') as swagger_yaml:
            contents = swagger_yaml.read()
            swagger_string = contents.decode()
            specification = yaml.safe_load(swagger_string)  # type: dict
        specification['host'] = 'localhost'
        flask_app.add_api(specification)

        api_server_client = flask_app.app.test_client()

    return api_server_client
