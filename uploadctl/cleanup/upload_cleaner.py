import os

# import logging
# logging.basicConfig()
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

import boto3
from botocore.exceptions import ClientError

from hca.util.pool import ThreadPool

from upload.common.database_orm import DBSessionMaker, DbFile, DbChecksum, DbValidation

"""
TODO:
populate s3_etag column for files we have
delete file,checksum,validation,notification records for files we don't.

Iterate through every File in the database
"""
import time

import signal
import sys
from threading import Lock

stats = {
    'deleted': 0,
    'etag_added': 0,
    'already_good': 0
}
stats_lock = Lock()


def signal_handler(sig, frame):
    global stats

    print("\n" + str(stats))
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


class UploadCleaner:

    CLEAR_TO_EOL = "\x1b[0K"

    class DontDelete(RuntimeError):
        pass

    def __init__(self, options):
        self.options = options
        self.s3 = boto3.resource('s3')
        self.bucket = self.s3.Bucket(f"org-humancellatlas-upload-{os.environ['DEPLOYMENT_STAGE']}")
        self.db_session_maker = DBSessionMaker()

    def clean_files(self):
        """
        Delete entries from file,checksum,validation,notification DB tables for which this is no file in S3.
        For files that are is S3, ensure the s3_etag is up to date in the DB file record.
        """
        global stats

        session = self.db_session_maker.session()
        t1 = time.time()
        files_id_list = []
        # TODO: sam remove filter after this run
        for file in session.query(DbFile).filter(DbFile.s3_etag == None):  # noqa
            files_id_list.append(file.id)
        t2 = time.time()
        print(f"Retrieved {len(files_id_list)} files in {t2-t1}")
        session.close()

        pool = ThreadPool(self.options.jobs)
        for file_id in files_id_list:
            pool.add_task(self._clean_file, file_id)
        pool.wait_for_completion()
        print("\n" + str(stats))

    def _clean_file(self, file_id):
        output = f"{file_id}: "
        session = self.db_session_maker.session()
        file = session.query(DbFile).get(file_id)
        obj = self.bucket.Object(file_id)
        try:
            obj.load()
            output += "exists in S3... "
            e_tag = obj.e_tag.strip('\"')
            if file.s3_etag and file.s3_etag == e_tag:
                self._increment_stat('already_good')
                output += "already good."
            else:
                output += "adding etag to file record."
                file.s3_etag = e_tag
                session.add(file)
                self._increment_stat('etag_added')
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                output += "is not in S3, deleting."
                session.delete(file)
                self._increment_stat('deleted')
            else:
                print(e)
                raise
        print(output)
        session.commit()
        session.close()

    def _increment_stat(self, stat):
        global stats, stats_lock

        with stats_lock:
            stats[stat] += 1
