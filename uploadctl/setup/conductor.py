from .component import CompositeComponent
from .upload_bucket import UploadBucketAssembly


class SetupConductor(CompositeComponent):

    SUBCOMPONENTS = {
        'bucket': UploadBucketAssembly,
    }

    def __str__(self):
        return ''
