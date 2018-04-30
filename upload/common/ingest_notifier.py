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

    def __init__(self):
        self.notification_id = str(uuid.uuid4())
        self.ingest_amqp_server = os.environ['INGEST_AMQP_SERVER']
        logger.debug("starting")
        self.connect()

    def connect(self):
        logger.debug(f"connecting to {self.ingest_amqp_server}")
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.ingest_amqp_server))
        logger.debug(f"got connection {self.connection}")
        self.channel = self.connection.channel()
        logger.debug(f"got channel {self.channel}")
        retval = self.channel.queue_declare(queue=self.FILE_UPLOADED_QUEUE)
        logger.debug(f"declaring queue {self.FILE_UPLOADED_QUEUE} returned {retval}")

    def file_was_uploaded(self, file_info):
        upload_area_id = file_info["upload_area_id"]
        file_name = file_info["name"]
        self.file_key = upload_area_id + "/" + file_name
        format_logger_with_id(logger, "file_key", self.file_key)
        self.payload = file_info
        self.status = "DELIVERING"
        self._create_record()
        body = json.dumps(file_info)
        success = self.channel.basic_publish(exchange=self.FILE_UPLOAD_EXCHANGE,
                                             routing_key=self.FILE_UPLOADED_QUEUE,
                                             body=body)
        logger.debug(f"publish of {body} returned {success}")
        if not success:
            raise UploadException(status=requests.codes.server_error, title="Unexpected Error",
                                  detail=f"basic_publish to {self.ingest_amqp_server} returned {success}")
        self.connection.close()
        self.status = "DELIVERED"
        self._update_record()
        return success

    def _format_prop_vals_dict(self):
        vals_dict = {
            "id": self.notification_id,
            "payload": self.payload,
            "file_id": self.file_key,
            "status": self.status
        }
        return vals_dict

    def _create_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        create_pg_record("notification", prop_vals_dict)

    def _update_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        update_pg_record("notification", prop_vals_dict)
