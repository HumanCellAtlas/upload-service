import boto3

from staging import StagingArea, StagedFile


class ChecksumDaemon:

    def __init__(self, context):
        self._context = context
        self.log("Ahm ahliiivvve!")

    def consume_event(self, event):
        for record in event['Records']:
            if record['eventName'] != 'ObjectCreated:Put':
                self.log(f"WARNING: Unexpected event: {record['eventName']}")
                continue
            bucket = boto3.resource('s3').Bucket(record['s3']['bucket']['name'])
            file_key = record['s3']['object']['key']
            area_uuid = file_key.split('/')[0]
            staging_area = StagingArea(area_uuid)
            obj = bucket.Object(file_key)
            staged_file = StagedFile(staging_area, obj)
            staged_file.compute_checksums()
            staged_file.save_tags()

    def log(self, message):
        self._context.log(message)
