import os

os.environ['DEPLOYMENT_STAGE'] = 'test'
os.environ['UPLOAD_SERVICE_BUCKET_PREFIX'] = 'bogobucket-'


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
                del os.environ[k]

    def __exit__(self, type, value, traceback):
        for k, v in self.saved_vars.items():
            os.environ[k] = v
