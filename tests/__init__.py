import os


class EnvironmentSetup:

    def __init__(self, env_vars_dict):
        self.env_vars = env_vars_dict
        self.saved_vars = {}

    def __enter__(self):
        for k, v in self.env_vars.items():
            if k in os.environ:
                self.saved_vars[k] = os.environ[k]
            os.environ[k] = v

    def __exit__(self, type, value, traceback):
        for k, v in self.saved_vars.items():
            os.environ[k] = v
