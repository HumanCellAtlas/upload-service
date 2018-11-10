import os
import sys
import pathlib
import subprocess
import time
import urllib.parse

import boto3
from urllib3.util import parse_url

from upload.common.validation_event import UploadedFileValidationEvent
from upload.common.logging import get_logger
from upload.common.logging import format_logger_with_id
from upload.common.upload_api_client import update_event


logger = get_logger(f"CHECKSUMMER [{os.environ.get('AWS_BATCH_JOB_ID')}]")


class ValidatorHarness:

    DEFAULT_STAGING_AREA = "/data"
    TIMEOUT = None

    def __init__(self, path_to_validator, s3_url_of_file_to_be_validated, staging_folder=None):
        self.path_to_validator = path_to_validator
        url_bits = parse_url(s3_url_of_file_to_be_validated)
        self.s3_bucket_name = url_bits.netloc
        self.s3_object_key = urllib.parse.unquote(url_bits.path.lstrip('/'))
        self.staging_folder = staging_folder or self.DEFAULT_STAGING_AREA
        self.version = self._find_version()
        self.job_id = os.environ['AWS_BATCH_JOB_ID']
        self.validation_id = os.environ['VALIDATION_ID']
        self._log("VALIDATOR STARTING version={version}, job_id={job_id}, "
                  "validation_id={validation_id} attempt={attempt}".format(
                      version=self.version,
                      job_id=self.job_id,
                      validation_id=self.validation_id,
                      attempt=os.environ['AWS_BATCH_JOB_ATTEMPT']))

    def validate(self, test_only=False):
        key_parts = self.s3_object_key.split('/')
        upload_area_id = key_parts.pop(0)
        file_name = "/".join(key_parts)
        format_logger_with_id(logger, "file_key", self.s3_object_key)
        self._log("VERSION {version}, attempt {attempt} with argv: {argv}".format(
            version=self.version, attempt=os.environ['AWS_BATCH_JOB_ATTEMPT'], argv=sys.argv))

        self._stage_file_to_be_validated()

        validation_event = UploadedFileValidationEvent(file_id=self.s3_object_key,
                                                       validation_id=self.validation_id,
                                                       job_id=self.job_id,
                                                       status="VALIDATING")
        if not test_only:
            update_event(validation_event, {"upload_area_id": upload_area_id, "name": file_name})

        results = self._run_validator()

        results["upload_area_id"] = upload_area_id
        results["name"] = file_name
        validation_event.status = "VALIDATED"

        if not test_only:
            update_event(validation_event, results)

        self._unstage_file()

    def _stage_file_to_be_validated(self):
        s3 = boto3.resource('s3')
        self.staged_file_path = os.path.join(self.staging_folder, self.s3_object_key)
        self._log("Staging s3://{bucket}/{key} at {file_path}".format(bucket=self.s3_bucket_name,
                                                                      key=self.s3_object_key,
                                                                      file_path=self.staged_file_path))
        pathlib.Path(os.path.dirname(self.staged_file_path)).mkdir(parents=True, exist_ok=True)
        s3.Bucket(self.s3_bucket_name).download_file(self.s3_object_key, self.staged_file_path)

    def _run_validator(self):
        command = [self.path_to_validator, self.staged_file_path]
        os.environ['VALIDATION_ID'] = self.validation_id
        start_time = time.time()
        self._log("RUNNING {}".format(command))
        results = {
            'validation_id': self.validation_id,
            'command': " ".join(command),
            'exit_code': None,
            'status': None,
            'stdout': None,
            'stderr': None,
            'duration_s': None,
            'exception': None
        }
        try:
            completed_process = subprocess.run(command,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE,
                                               timeout=self.TIMEOUT)
            self._log("validator completed")
            results['status'] = 'completed'
            results['exit_code'] = completed_process.returncode
            results['stdout'] = completed_process.stdout.decode('utf8')
            results['stderr'] = completed_process.stderr.decode('utf8')
        except subprocess.TimeoutExpired as e:
            self._log("validator timed out: {}".format(e))
            results['status'] = 'timed_out'
            results['stdout'] = e.stdout.decode('utf8')
            results['stderr'] = e.stderr.decode('utf8')
        except Exception as e:
            self._log("validator aborted: {}".format(e))
            results['status'] = 'aborted'
            results['exception'] = e
        results['duration_s'] = time.time() - start_time
        return results

    def _unstage_file(self):
        self._log("removing file {}".format(self.staged_file_path))
        os.remove(self.staged_file_path)

    def _find_version(self):
        try:
            with open('/HARNESS_VERSION', 'r') as fp:
                return fp.read().strip()
        except FileNotFoundError:
            return None

    def _log(self, message):
        logger.info("[{id}]: ".format(id=self.job_id) + str(message))
