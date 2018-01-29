from .component import CompositeComponent
from .upload_bucket import UploadBucketAssembly
from .slack_feed import SlackFeed
from .upload_api import UploadApi


class SetupConductor(CompositeComponent):

    SUBCOMPONENTS = {
        'bucket': UploadBucketAssembly,
        'slack-feed': SlackFeed,
        'upload-api': UploadApi,
    }

    def __str__(self):
        return ''
