#!/usr/bin/env python3.6

"""
Upload Service administration tool

    upload -e [dev,staging,integration] cleanup              Remove staging areas 3 days old or older
    upload -e [dev,staging,integration] amqp publish|listen  Test AMQP
"""


import argparse
from datetime import datetime, timezone
import os
import re
import sys
import dateutil.parser

import boto3
import pika

if __name__ == '__main__':  # noqa
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from upload import UploadArea


iam = boto3.client('iam')


class UploadCleaner:

    CLEAR_TO_EOL = "\x1b[0K"

    class DontDelete(RuntimeError):
        pass

    def __init__(self, deployment, clean_older_than_days=2, ignore_file_age=False, dry_run=False):
        self.deployment = deployment
        self.clean_older_than_days = clean_older_than_days
        self.ignore_file_age = ignore_file_age
        self.dry_run = dry_run
        self.now = datetime.now(timezone.utc)
        os.environ['DEPLOYMENT_STAGE'] = deployment  # to communicate to UploadArea
        self.counts = {
            'users': 0,
            'matching_users': 0,
            'old_users': 0
        }
        self.clean()

    def clean(self):
        for user in self._iam_users():
            try:
                username = user['UserName']
                sys.stdout.write(f"\r{username} {self.CLEAR_TO_EOL}")
                self.counts['users'] += 1
                self._check_username_matches_deployment(username)
                self._check_if_user_used_recently(user)

                upload_area_uuid = '-'.join(user['UserName'].split("-")[3:])
                self._check_special_case_upload_areas(upload_area_uuid)

                area = UploadArea(upload_area_uuid)
                self._check_if_files_modified_recently(area)

                print("DELETE.")
                if not self.dry_run:
                    area.delete()

            except self.DontDelete:
                pass
            sys.stdout.flush()

        print("Users: {user_count} matching {matching_count} deleted {deleted_count}".format(
            user_count=self.counts['users'],
            matching_count=self.counts['matching_users'],
            deleted_count=self.counts['old_users']
        ))

    def _check_username_matches_deployment(self, username):
        regex = f"^upload-{self.deployment}-user-"
        if re.match(regex, username):
            sys.stdout.write(f"matches, ")
            self.counts['matching_users'] += 1
        else:
            raise self.DontDelete()

    def _check_if_user_used_recently(self, user):
        used_ago = self.now - self._user_last_used_at(user)
        sys.stdout.write(f"user used {used_ago.days} days ago, ")
        if used_ago.days <= self.clean_older_than_days:
            print("skipping.")
            raise self.DontDelete()
        else:
            self.counts['old_users'] += 1

    def _user_last_used_at(self, user):
        """ Return latest date that a user account was used or a file modified in the upload area """
        last_used = user['CreateDate']
        for key in iam.list_access_keys(UserName=user['UserName'])['AccessKeyMetadata']:
            if key['CreateDate'] > last_used:
                last_used = key['CreateDate']
            key_last_used = iam.get_access_key_last_used(AccessKeyId=key['AccessKeyId'])['AccessKeyLastUsed']
            if 'LastUsedDate' in key_last_used and key_last_used['LastUsedDate'] > last_used:
                last_used = key_last_used['LastUsedDate']
        return last_used

    def _check_special_case_upload_areas(self, area_uuid):
        if re.match('aaaaaaaa-bbbb-cccc-dddd-.*', area_uuid):
            print("special case.")
            raise self.DontDelete

    def _check_if_files_modified_recently(self, upload_area):
        if self.ignore_file_age:
            return
        used_ago = self.now - self._files_last_modified_at(upload_area)
        sys.stdout.write(f"files used {used_ago.days} days ago, ")
        if used_ago.days <= self.clean_older_than_days:
            print("skipping.")
            raise self.DontDelete()

    def _files_last_modified_at(self, upload_area):
        last_file_modified_at = datetime.fromtimestamp(0, tz=timezone.utc)
        files = upload_area.ls()['files']
        sys.stdout.write(f"{len(files)} files, ")
        for file in files:
            print(file)
            file_last_modified = dateutil.parser.parse(file['last_modified'])
            if file_last_modified > last_file_modified_at:
                last_file_modified_at = file_last_modified
        return last_file_modified_at

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
cleanup_parser.add_argument('--age-days', type=int, default=3, help="delete areas older than this")
cleanup_parser.add_argument('--ignore-file-age', action='store_true', help="ignore age of files in bucket")
cleanup_parser.add_argument('--dry-run', action='store_true', help="examine but don't take action")

amqp_parser = subparsers.add_parser('amqp')
amqp_parser.set_defaults(command='amqp')
amqp_parser.add_argument('amqp_command', choices=['publish', 'listen'])
amqp_parser.add_argument('queue_name', nargs='?', default='ingest.sam.test')
amqp_parser.add_argument('-e', '--exchange', default=FILE_UPLOAD_EXCHANGE)
amqp_parser.add_argument('-s', '--server', default=INGEST_AMQP_SERVER)


args = parser.parse_args()

if args.command == 'cleanup':
    UploadCleaner(args.deployment,
                  clean_older_than_days=args.age_days,
                  ignore_file_age=args.ignore_file_age,
                  dry_run=args.dry_run)
elif args.command == 'amqp':
    if args.amqp_command == 'listen':
        tool = AmqpTool(server=args.server, exchange_name=args.exchange, queue_name=args.queue_name)
        tool.create_queue()
        tool.listen()
    elif args.amqp_command == 'publish':
        tool = AmqpTool(server=args.server, exchange_name=args.exchange, queue_name=args.queue_name)
        tool.publish()

