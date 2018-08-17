from dcplib.config import Config


class UploadConfig(Config):

    def __init__(self, *args, **kwargs):
        super().__init__('upload', **kwargs)


class UploadVersion(Config):
    def __init__(self, *args, **kwargs):
        super().__init__(component_name='upload', secret_name='upload_service_version', **kwargs)
