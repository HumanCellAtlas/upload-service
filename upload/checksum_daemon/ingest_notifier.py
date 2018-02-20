import json
import os

import pika
import requests

from .. import UploadException
from ..logging import get_logger

logger = get_logger(__name__)


class IngestNotifier:

    FILE_UPLOAD_EXCHANGE = 'ingest.file.staged.exchange'
    FILE_UPLOADED_QUEUE = 'ingest.file.create.staged'

    def __init__(self):
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
        body = json.dumps(file_info)
        success = self.channel.basic_publish(exchange=self.FILE_UPLOAD_EXCHANGE,
                                             routing_key=self.FILE_UPLOADED_QUEUE,
                                             body=body)
        logger.debug(f"publish of {body} returned {success}")
        if not success:
            raise UploadException(status=requests.codes.server_error, title="Unexpected Error",
                                  detail=f"basic_publish to {self.ingest_amqp_server} returned {success}")
        self.connection.close()
        return success
