import json
import logging

from upload.common.logging import configure_logger
from upload.common.upload_area import UploadArea
from upload.common.validation_scheduler import ValidationScheduler

configure_logger()
logger = logging.getLogger(__name__)


# This lambda function is invoked by messages in the the validation_queue (AWS SQS).
# The queue and the lambda function are connected via aws_lambda_event_source_mapping
def schedule_file_validation(event, context):
    logger.info(f"initiated schedule_file_validation with {event}")
    unwrapped_event = json.loads(event["Records"][0]["body"])
    upload_area_uuid = unwrapped_event["upload_area_uuid"]
    filenames = unwrapped_event["filenames"]
    validation_id = unwrapped_event["validation_id"]
    image = unwrapped_event["validator_docker_image"]
    env = unwrapped_event["environment"]
    orig_validation_id = unwrapped_event["orig_validation_id"]
    upload_area = UploadArea(upload_area_uuid)
    files = []
    for filename in filenames:
        file = upload_area.uploaded_file(filename)
        files.append(file)
    validation_scheduler = ValidationScheduler(upload_area_uuid, files)
    validation_id = validation_scheduler.schedule_batch_validation(validation_id, image, env, orig_validation_id)
    logger.info(f"scheduled batch job with {event}")
