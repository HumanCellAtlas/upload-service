import json
import os
import uuid
import pika
import requests

from .exceptions import UploadException
from .logging import get_logger
from .logging import format_logger_with_id
from .database import create_pg_record, update_pg_record

logger = get_logger(__name__)


class IngestNotifier:

    FILE_UPLOAD_EXCHANGE = 'ingest.file.staged.exchange'
    FILE_UPLOADED_QUEUE = 'ingest.file.create.staged'

    FILE_VALIDATED_EXCHANGE = "ingest.validation.exchange"
    FILE_VALIDATED_QUEUE = "ingest.file.validation.queue"

    def __init__(self, notification_type):
        if notification_type == "file_uploaded":
            self.exchange = self.FILE_UPLOAD_EXCHANGE
            self.queue = self.FILE_UPLOADED_QUEUE
        elif notification_type == "file_validated":
            self.exchange = self.FILE_VALIDATED_EXCHANGE
            self.queue = self.FILE_VALIDATED_QUEUE
        else:
            raise Exception("Unknown notification type for ingest")
        self.ingest_amqp_server = os.environ['INGEST_AMQP_SERVER']
        logger.debug("starting")
        self.connect()

    def connect(self):
        logger.debug(f"connecting to {self.ingest_amqp_server}")
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.ingest_amqp_server))
        logger.debug(f"got connection {self.connection}")
        self.channel = self.connection.channel()
        logger.debug(f"got channel {self.channel}")
        retval = self.channel.queue_declare(queue=self.queue)
        logger.debug(f"declaring queue {self.queue} returned {retval}")

    def format_and_send_notification(self, file_info):
        notification_props = self._format_notification_props(file_info)
        notification_props["status"] = "DELIVERING"
        format_logger_with_id(logger, "file_key", notification_props["file_id"])
        create_pg_record("notification", notification_props)
        body = json.dumps(file_info)
        success = self._publish_notification(body)
        notification_props["status"] = "DELIVERED"
        update_pg_record("notification", notification_props)
        return success

    def _publish_notification(self, body):
        success = self.channel.basic_publish(exchange=self.exchange,
                                             routing_key=self.queue,
                                             body=body)
        logger.debug(f"publish of {body} returned {success}")
        if not success:
            raise UploadException(status=requests.codes.server_error, title="Unexpected Error",
                                  detail=f"basic_publish to {self.ingest_amqp_server} returned {success}")
        self.connection.close()
        return success

    def _format_notification_props(self, file_info):
        upload_area_id = file_info["upload_area_id"]
        file_name = file_info["name"]
        notification_props = {
            "id": str(uuid.uuid4()),
            "file_id": f"{upload_area_id}/{file_name}",
            "payload": file_info
        }
        return notification_props
