import re
import sys
import dateutil.parser
from datetime import datetime, timezone

import boto3

from upload import UploadArea


class UploadCleaner:

    """
    Find and delete old Upload Areas
    """

    CLEAR_TO_EOL = "\x1b[0K"

    class DontDelete(RuntimeError):
        pass

    def __init__(self, deployment, clean_older_than_days=2, ignore_file_age=False, dry_run=False):
        self.iam = boto3.client('iam')
        self.deployment = deployment
        self.clean_older_than_days = clean_older_than_days
        self.ignore_file_age = ignore_file_age
        self.dry_run = dry_run
        self.now = datetime.now(timezone.utc)
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

                upload_area_uuid = '-'.join(user['UserName'].split("-")[3:])
                self._check_special_case_upload_areas(upload_area_uuid)

                self._check_if_user_used_recently(user)

                area = UploadArea(upload_area_uuid)
                self._check_if_files_modified_recently(area)

                print("DELETE.")
                if not self.dry_run:
                    area.delete()

            except self.DontDelete:
                pass
            sys.stdout.flush()

        print("\rUsers={user_count} matching={matching_count} deleted={deleted_count}".format(
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
        for key in self.iam.list_access_keys(UserName=user['UserName'])['AccessKeyMetadata']:
            if key['CreateDate'] > last_used:
                last_used = key['CreateDate']
            key_last_used = self.iam.get_access_key_last_used(AccessKeyId=key['AccessKeyId'])['AccessKeyLastUsed']
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

    def _iam_users(self):
        marker = None
        while True:
            if marker:
                resp = self.iam.list_users(Marker=marker)
            else:
                resp = self.iam.list_users()
            for user in resp['Users']:
                yield user
            if 'Marker' in resp:
                marker = resp['Marker']
            else:
                break
