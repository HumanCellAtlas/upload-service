import os

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

    def __enter__(self):
        for k, v in self.env_vars.items():
            if k in os.environ:
                self.saved_vars[k] = os.environ[k]
            if v:
                os.environ[k] = v
            else:
                if k in os.environ:
                    del os.environ[k]

    def __exit__(self, type, value, traceback):
        for k, v in self.saved_vars.items():
            os.environ[k] = v


FIXTURE_DATA_CHECKSUMS = {
    'exquisite corpse': {
        'checksums': {
            "s3_etag": "18f17fbfdd21cf869d664731e10d4ffd",
            "sha1": "b1b101e21cf9cf8a4729da44d7818f935eec0ce8",
            "sha256": "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70",
            "crc32c": "FE9ADA52"
        },
        's3_tagset': [
            {'Key': "hca-dss-s3_etag", 'Value': "18f17fbfdd21cf869d664731e10d4ffd"},
            {'Key': "hca-dss-sha1", 'Value': "b1b101e21cf9cf8a4729da44d7818f935eec0ce8"},
            {'Key': "hca-dss-sha256", 'Value': "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70"},
            {'Key': "hca-dss-crc32c", 'Value': "FE9ADA52"}
        ]
    }
}


def fixture_file_path(filename):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 'fixtures', filename))
