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


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('-d', '--deployment', choices=['dev', 'integration', 'staging'], default='dev')
parser.add_argument('--dry-run', action='store_true')
parser.add_argument('command', choices=['cleanup'])
args = parser.parse_args()

if args.command == 'cleanup':
    UploadCleaner(args.deployment, args.dry_run)
