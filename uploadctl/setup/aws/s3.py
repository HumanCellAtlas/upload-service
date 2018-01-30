import time

import boto3
from botocore.client import ClientError

from ..component import Component, AttributeComponent


class Bucket(Component):

    def __init__(self, name, **options):
        self.name = name
        super().__init__(**options)
        self.s3 = boto3.resource('s3')

    def __str__(self):
        return f"Bucket {self.name}"

    def is_setup(self):
        try:
            self.s3.meta.client.head_bucket(Bucket=self.name)
            return True
        except ClientError:
            # The bucket does not exist or you have no access.
            return False

    def set_it_up(self):
        self.s3.Bucket(self.name).create()

    def tear_it_down(self):
        self._empty()
        self.s3.Bucket(self.name).delete()
        time.sleep(1)

    def _empty(self):
        paginator = self.s3.meta.client.get_paginator('list_objects')
        for page in paginator.paginate(Bucket=self.name):
            if 'Contents' in page:
                for o in page['Contents']:
                    self.s3.meta.client.delete_object(Bucket=self.name, Key=o['Key'])


class BucketTransferAcceleration(AttributeComponent):

    def __init__(self, bucket_name, **options):
        self.bucket_name = bucket_name
        super().__init__(**options)
        self.s3client = boto3.client('s3')

    def __str__(self):
        return f"Bucket {self.bucket_name} acceleration"

    def is_setup(self):
        try:
            response = self.s3client.get_bucket_accelerate_configuration(
                Bucket=self.bucket_name
            )
            return 'Status' in response and response['Status'] == 'Enabled'
        except ClientError:
            return False

    def set_it_up(self):
        self.s3client.put_bucket_accelerate_configuration(
            Bucket=self.bucket_name,
            AccelerateConfiguration={'Status': 'Enabled'}
        )

    def tear_it_down(self):
        self.s3client.put_bucket_accelerate_configuration(
            Bucket=self.bucket_name,
            AccelerateConfiguration={'Status': 'Suspended'}
        )

