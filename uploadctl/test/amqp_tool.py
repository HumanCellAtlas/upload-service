import os

import pika


class AmqpTool:

    FILE_UPLOAD_EXCHANGE = 'ingest.file.staged.exchange'

    def __init__(self, server, exchange_name, queue_name):
        self.server = server if server else os.environ['INGEST_AMQP_SERVER']
        self.exchange_name = exchange_name if exchange_name else self.FILE_UPLOAD_EXCHANGE
        self.queue_name = queue_name
        self.connection = None
        self.channel = None
        self.connect()

    def connect(self):
        parameters = pika.connection.ConnectionParameters(host=self.server)
        self.connection = pika.BlockingConnection(parameters)
        print(f"Connection {self.connection}")
        self.channel = self.connection.channel()
        print(f"Channel {self.channel}")

    def create_queue(self):
        retval = self.channel.queue_declare(queue=self.queue_name)
        print(f"declaring queue {self.queue_name} returned {retval}")
        retval = self.channel.queue_bind(self.queue_name, self.exchange_name)
        print(f"queue_bind returned {retval}")

    def _on_message(self, channel, method, properties, body):
        print(f"on_message: {body}")

    def listen(self):
        resp = self.channel.basic_consume(self._on_message, queue=self.queue_name, no_ack=True)
        print(f"basic_consume returned {resp}")
        self.channel.start_consuming()

    def publish(self):
        success = self.channel.basic_publish(exchange=self.exchange_name,
                                             routing_key=self.queue_name,
                                             body='{"this_is": "a_test"}')
        print(f"publish returned {success}")
