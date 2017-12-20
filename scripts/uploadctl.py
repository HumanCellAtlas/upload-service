#!/usr/bin/env python3.6

"""
Miscellaneous Upload Service administration tool
"""

# upload -e [dev,staging,prod] cleanup

import argparse
from datetime import datetime, timezone
import os
import re
import sys

import boto3
import pika

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from upload import UploadArea


iam = boto3.client('iam')


class UploadCleaner:

    def __init__(self, deployment, dry_run):
        self.deployment = deployment
        self.dry_run = dry_run
        self.now = datetime.now(timezone.utc)
        self.clean()
        os.environ['DEPLOYMENT_STAGE'] = deployment  # for UploadArea

    def clean(self):
        counts = {
            'users': 0,
            'matching_users': 0,
            'old_users': 0
        }
        for user in self._iam_users():
            counts['users'] += 1
            if self._name_matches_deployment(user['UserName']):
                counts['matching_users'] += 1
                upload_area_uuid = '-'.join(user['UserName'].split("-")[3:])
                area = UploadArea(upload_area_uuid)
                last_used_at = self._last_used_at(area, user)
                if self._not_recent(last_used_at):
                    counts['old_users'] += 1
                    print(f"Last used {(self.now - last_used_at).days} days ago {user['UserName']}")
                    if not self.dry_run:
                        area.delete()

        print(f"Users: {counts['users']} matching {counts['matching_users']} deleted {counts['old_users']}")

    def _name_matches_deployment(self, username):
        regex = f"^upload-{self.deployment}-user-"
        return re.match(regex, username)

    def _not_recent(self, when):
        ago = self.now - when
        return ago.days > 2

    def _last_used_at(self, upload_area, user):
        """ Return latest date that a user account was used or a file modified in the upload area """
        last_used = user['CreateDate']

        for key in iam.list_access_keys(UserName=user['UserName'])['AccessKeyMetadata']:
            if key['CreateDate'] > last_used:
                last_used = key['CreateDate']

            key_last_used = iam.get_access_key_last_used(AccessKeyId=key['AccessKeyId'])['AccessKeyLastUsed']
            if 'LastUsedDate' in key_last_used and key_last_used['LastUsedDate'] > last_used:
                last_used = key_last_used['LastUsedDate']

        if not self.dry_run:  # because it is slow
            for file in upload_area.ls()['files']:
                if file['last_modified'] > last_used:
                    last_used = file['last_modified']

        return last_used

    @staticmethod
    def _iam_users():
        marker = None
        while True:
            if marker:
                resp = iam.list_users(Marker=marker)
            else:
                resp = iam.list_users()
            for user in resp['Users']:
                yield user
            if 'Marker' in resp:
                marker = resp['Marker']
            else:
                break



INGEST_AMQP_SERVER = f"amqp.ingest.{os.environ['DEPLOYMENT_STAGE']}.data.humancellatlas.org"
FILE_UPLOAD_EXCHANGE = 'ingest.file.staged.exchange'


class AmqpTool:
    def __init__(self, server, exchange_name, queue_name):
        self.server = server
        self.exchange_name = exchange_name
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


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('-d', '--deployment', choices=['dev', 'integration', 'staging'], default='dev')
subparsers = parser.add_subparsers()

cleanup_parser = subparsers.add_parser('cleanup')
cleanup_parser.set_defaults(command='cleanup')
cleanup_parser.add_argument('--dry-run', action='store_true', help="examine but don't take action")

amqp_parser = subparsers.add_parser('amqp')
amqp_parser.set_defaults(command='amqp')
amqp_parser.add_argument('amqp_command', choices=['publish', 'listen'])
amqp_parser.add_argument('queue_name', nargs='?', default='ingest.sam.test')
amqp_parser.add_argument('-e', '--exchange', default=FILE_UPLOAD_EXCHANGE)
amqp_parser.add_argument('-s', '--server', default=INGEST_AMQP_SERVER)


args = parser.parse_args()

if args.command == 'cleanup':
    UploadCleaner(args.deployment, args.dry_run)
elif args.command == 'amqp':
    if args.amqp_command == 'listen':
        tool = AmqpTool(server=args.server, exchange_name=args.exchange, queue_name=args.queue_name)
        tool.create_queue()
        tool.listen()
    elif args.amqp_command == 'publish':
        tool = AmqpTool(server=args.server, exchange_name=args.exchange, queue_name=args.queue_name)
        tool.publish()

