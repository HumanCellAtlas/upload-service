from .component import CompositeComponent
from .upload_bucket import UploadBucketAssembly
from .slack_feed import SlackFeed
from .upload_api import UploadApi
from .checksum_daemon import ChecksumDaemon


class SetupConductor(CompositeComponent):

    SUBCOMPONENTS = {
        'bucket': UploadBucketAssembly,
        'slack-feed': SlackFeed,
        'upload-api': UploadApi,
        'checksum-daemon': ChecksumDaemon,
    }

    def __str__(self):
        return ''
