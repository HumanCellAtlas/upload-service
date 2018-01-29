from .component import CompositeComponent
from .upload_bucket import UploadBucketAssembly
from .slack_feed import SlackFeed


class SetupConductor(CompositeComponent):

    SUBCOMPONENTS = {
        'bucket': UploadBucketAssembly,
        'slack-feed': SlackFeed,
    }

    def __str__(self):
        return ''
