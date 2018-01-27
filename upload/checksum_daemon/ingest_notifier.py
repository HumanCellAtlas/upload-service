import json
import os

import pika
import requests

from .. import UploadException


class IngestNotifier:

    FILE_UPLOAD_EXCHANGE = 'ingest.file.staged.exchange'
    FILE_UPLOADED_QUEUE = 'ingest.file.create.staged'

    def __init__(self, logfunc=None):
        self.ingest_amqp_server = os.environ['INGEST_AMQP_SERVER']
        self.logfunc = logfunc
        self.debug("starting")
        self.connect()

    def connect(self):
        self.debug(f"connecting to {self.ingest_amqp_server}")
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.ingest_amqp_server))
        self.debug(f"got connection {self.connection}")
        self.channel = self.connection.channel()
        self.debug(f"got channel {self.channel}")
        retval = self.channel.queue_declare(queue=self.FILE_UPLOADED_QUEUE)
        self.debug(f"declaring queue {self.FILE_UPLOADED_QUEUE} returned {retval}")

    def file_was_uploaded(self, file_info):
        body = json.dumps(file_info)
        success = self.channel.basic_publish(exchange=self.FILE_UPLOAD_EXCHANGE,
                                             routing_key=self.FILE_UPLOADED_QUEUE,
                                             body=body)
        self.debug(f"publish of {body} returned {success}")
        if not success:
            raise UploadException(status=requests.codes.server_error, title="Unexpected Error",
                                  detail=f"basic_publish to {self.ingest_amqp_server} returned {success}")
        self.connection.close()
        return success

    def debug(self, message):
        if self.logfunc:
            self.logfunc("IngestNotifier " + message)
