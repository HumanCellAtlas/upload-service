import json, os

import pika, requests

from .. import StagingException


class IngestNotifier:

    INGEST_AMQP_SERVER = f"amqp.ingest.{os.environ['DEPLOYMENT_STAGE']}.data.humancellatlas.org"

    def file_was_staged(self, file_info):
        connection = pika.BlockingConnection(pika.ConnectionParameters(self.INGEST_AMQP_SERVER))
        channel = connection.channel()
        channel.queue_declare(queue='ingest.file.create.staged')
        success = channel.basic_publish(exchange='ingest.file.staged.exchange',
                                        routing_key='ingest.file.create.staged',
                                        body=json.dumps(file_info))
        if not success:
            raise StagingException(status=requests.codes.server_error, title="Unexpected Error",
                                   detail=f"basic_publish to {self.INGEST_AMQP_SERVER} returned {success}")
        connection.close()
        return success
