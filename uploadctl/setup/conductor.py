from proforma import CompositeComponent
from .upload_bucket import UploadBucketAssembly
from .upload_api import UploadApi
from .checksum_daemon import ChecksumDaemon
from .batch_shared import BatchSharedConfig
from .batch_validation import BatchValidation


class SetupConductor(CompositeComponent):

    SUBCOMPONENTS = {
        'bucket': UploadBucketAssembly,
        'upload-api': UploadApi,
        'checksum-daemon': ChecksumDaemon,
        'batch-shared': BatchSharedConfig,
        'validation': BatchValidation,
    }

    def __str__(self):
        return ''  # Don't announce name at top level
