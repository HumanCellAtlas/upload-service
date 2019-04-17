import json

import boto3
from tenacity import retry, wait_fixed, stop_after_attempt

from .exceptions import UploadException
from .logging import get_logger

logger = get_logger(__name__)


class SQSQueue:
    """ This class encapsulates logic related to adding items from an SQS (Amazon Simple Queue Service)."""

    def __init__(self, queue_url, payload, error_message):
        self.sqs = boto3.resource('sqs')
        self.queue_url = queue_url
        self.payload = payload
        self.error_message = error_message

    @retry(reraise=True, wait=wait_fixed(2), stop=stop_after_attempt(5))
    def enqueue(self):
        """ Add a payload to SQS. If the addition was not successful, throw an UploadException citing the error."""
        response = None
        try:
            response = self.sqs.meta.client.send_message(QueueUrl=self.queue_url,
                                                         MessageBody=json.dumps(self.payload))
            status = response['ResponseMetadata']['HTTPStatusCode']
            if status != 200:
                raise UploadException(status=500, title="Internal error",
                                      detail=self.error_message)
        except Exception as err:
            raise UploadException(status=500, title="Internal error",
                                  detail=f"Unable to send message to SQS client with error: {err}") from err


class CsumSQSQueue(SQSQueue):
    """ This class encapsulates the information that is needed to add items to SQS for the purpose of checksumming files
    after they have been uploaded to an UploadArea."""

    def __init__(self, upload_area, filename):
        _url = upload_area.config.csum_upload_q_url
        _payload = {
            'Records': [{
                'eventName': 'ObjectCreated:Put',
                "s3": {
                    "bucket": {
                        "name": f"{upload_area.bucket_name}"
                    },
                    "object": {
                        "key": f"{upload_area.key_prefix}{filename}"
                    }
                }
            }]
        }
        _error_message = f"Adding file upload message for {upload_area.key_prefix}{filename} was unsuccessful to " \
            f"SQS {_url}"

        SQSQueue.__init__(self, _url, _payload, _error_message)


class DeletionSQSQueue(SQSQueue):
    """ This class encapsulates information that is required to add items to SQS for the purpose of deleting
    UploadAreas. """

    def __init__(self, upload_area):
        _url = upload_area.config.area_deletion_q_url
        _payload = {
            'area_uuid': f"{upload_area.uuid}"
        }
        _error_message = f"Adding delete message for area {upload_area.uuid} was unsuccessful to SQS {_url}"

        SQSQueue.__init__(self, _url, _payload, _error_message)
