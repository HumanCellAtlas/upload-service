import os

from preform import CompositeComponent
from preform.aws import Bucket, BucketTransferAcceleration


class UploadBucket(Bucket):

    def __init__(self, **options):
        # Danger: if BUCKET_NAME_TEMPLATE differs between deployments, this will not work.
        # This will get fixed when we switch to a YAML configuration.
        bucket_name = os.environ['BUCKET_NAME_TEMPLATE'].format(deployment_stage=os.environ['DEPLOYMENT_STAGE'])
        super().__init__(name=bucket_name, **options)


class UploadBucketTransferAcceleration(BucketTransferAcceleration):

    def __init__(self, **options):
        # Danger: if BUCKET_NAME_TEMPLATE differs between deployments, this will not work.
        # This will get fixed when we switch to a YAML configuration.
        bucket_name = os.environ['BUCKET_NAME_TEMPLATE'].format(deployment_stage=os.environ['DEPLOYMENT_STAGE'])
        super().__init__(bucket_name=bucket_name, **options)


class UploadBucketAssembly(CompositeComponent):

    SUBCOMPONENTS = {
        'bucket': UploadBucket,
        'bucket-accel': UploadBucketTransferAcceleration,
    }

    def __str__(self):
        return "Upload S3 bucket:"
