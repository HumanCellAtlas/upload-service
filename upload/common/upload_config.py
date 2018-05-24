from dcplib.config import Config


class UploadConfig(Config):

    def __init__(self, *args, **kwargs):
        super().__init__('upload', **kwargs)
