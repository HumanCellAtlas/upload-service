import json

from upload.common.logging import configure_logger
from upload.common.upload_area import UploadArea

configure_logger()


# This lambda function is invoked by messages in the the area_deletion_queue (AWS SQS).
# The queue and the lambda function are connected via aws_lambda_event_source_mapping
def delete_upload_area(event, context):
    unwrapped_event = json.loads(event["Records"][0]["body"])
    area_uuid = unwrapped_event["area_uuid"]
    UploadArea(area_uuid).delete()
