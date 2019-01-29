import json

from upload.common.uploaded_file import UploadedFile
from upload.common.validation_scheduler import ValidationScheduler
from upload.common.upload_area import UploadArea
from upload.common.logging import get_logger

logger = get_logger(__name__)


# This lambda function is invoked by messages in the the pre_batch_validation_queue (AWS SQS).
# The queue and the lambda function are connected via aws_lambda_event_source_mapping
def schedule_file_validation(event, context):
    logger.info(f"initiated schedule_file_validation with {event}")
    unwrapped_event = json.loads(event["Records"][0]["body"])
    upload_area_uuid = unwrapped_event["upload_area_uuid"]
    filename = unwrapped_event["filename"]
    validation_id = unwrapped_event["validation_id"]
    validator_image = unwrapped_event["validator_docker_image"]
    environment = unwrapped_event["environment"]
    orig_validation_id = unwrapped_event["orig_validation_id"]

    upload_area = UploadArea(upload_area_uuid)
    file = upload_area.uploaded_file(filename)
    validation_scheduler = ValidationScheduler(file)
    validation_id = validation_scheduler.schedule_batch_validation(validation_id,
    															   validator_image,
    															   environment,
    															   orig_validation_id)
    logger.info(f"scheduled batch job with {event}")
