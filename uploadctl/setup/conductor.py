from proforma import CompositeComponent
from .upload_api import UploadApi
from .checksum_daemon import ChecksumDaemon


class SetupConductor(CompositeComponent):

    SUBCOMPONENTS = {
        'upload-api': UploadApi,
        'checksum-daemon': ChecksumDaemon,
    }

    def __str__(self):
        return ''  # Don't announce name at top level
