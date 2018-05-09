import json
import os

from .aws_secret import AwsSecret
from .logging import get_logger

logger = get_logger(__name__)


class Config:

    """
    Implement singleton-like behavior using techniques from
    http://python-3-patterns-idioms-test.readthedocs.io/en/latest/Singleton.html.
    All instances of this class will share the same config data.
    If you subclass this class, the subclass gets its own data, but all
    instances of the subclass share that data.
    """

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_config'):
            cls.reset()
        return super().__new__(cls)

    """
    If source is specified, it must be the path to a JSON file
    """
    def __init__(self, component_name, deployment=None, source=None):
        super().__init__()
        self._component_name = component_name
        self._deployment = deployment or os.environ['DEPLOYMENT_STAGE']
        self._source = self._determine_source(source)

    @property
    def config(self):
        return self.__class__._config

    def __getattr__(self, name):
        if self.config_is_loaded():
            return self.value_from_config(name) \
                or self.value_from_env(name) \
                or self.raise_error(name)
        else:
            return self.value_from_env(name) \
                or (self.load() and self.value_from_config(name)) \
                or self.raise_error(name)

    @classmethod
    def reset(cls):
        cls._config = None
        cls.use_env = False

    """
    Bypass the load mechanism and set secrets directly.
    Used in testing.
    """
    def set(self, config):
        logger.debug(f"Setting config to {config}")
        self.__class__._config = config
        self.__class__.use_env = False

    def load(self):
        if self._source == 'aws':
            self.load_from_aws()
        else:
            self.load_from_file(self._source)
        return True  # so we can be used in 'and' statements

    def config_is_loaded(self):
        return self.config is not None

    def load_from_aws(self):
        secret_path = f"dcp/{self._component_name}/{self._deployment}/secrets"
        logger.debug(f"loading from AWS secret {secret_path}")
        secret = AwsSecret(secret_path)
        self.from_json(secret.value)

    def load_from_file(self, config_file_path):
        logger.debug(f"loading from {config_file_path}")
        with open(config_file_path, 'r') as config_fp:
            self.from_json(config_fp.read())

    def from_json(self, config_json):
        self.__class__._config = json.loads(config_json)

    def _determine_source(self, source):
        if source:
            pass
        elif 'CONFIG_SOURCE' in os.environ:
            source = os.environ['CONFIG_SOURCE']
        else:
            source = 'aws'
        return source

    def value_from_config(self, name):
        if name in self.config:
            # logger.debug(f"From config, {name} is {self.config[name]}")
            return self.config[name]
        else:
            return None

    def value_from_env(self, name):
        if self.__class__.use_env and name.upper() in os.environ:
            # logger.debug(f"from env, {name} is in {os.environ[name.upper()]}")
            return os.environ[name.upper()]
        else:
            return None

    def raise_error(self, name):
        raise RuntimeError(f"{name} is not in configuration")


class UploadConfig(Config):

    def __init__(self, *args, **kwargs):
        super().__init__('upload', **kwargs)
