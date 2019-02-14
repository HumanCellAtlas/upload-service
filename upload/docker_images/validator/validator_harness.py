import logging
import os
import pathlib
import subprocess
import sys
import time
import urllib.parse

import boto3
from tenacity import retry, stop_after_attempt, before_log, before_sleep_log, wait_exponential, TryAgain
from urllib3.util import parse_url

from upload.common.exceptions import UploadException
from upload.common.logging import get_logger
from upload.common.upload_api_client import update_event
from upload.common.validation_event import ValidationEvent

logger = get_logger(f"CHECKSUMMER [{os.environ.get('AWS_BATCH_JOB_ID')}]")


class ValidatorHarness:
    DEFAULT_STAGING_AREA = "/data"
    TIMEOUT = None

    def __init__(self, path_to_validator, s3_urls_of_files_to_be_validated, staging_folder=None):
        self.path_to_validator = path_to_validator
        self.s3_file_urls = s3_urls_of_files_to_be_validated
        self.staged_file_paths = []
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
        self._log("VERSION {version}, attempt {attempt} with argv: {argv}".format(
            version=self.version, attempt=os.environ['AWS_BATCH_JOB_ATTEMPT'], argv=sys.argv))

        upload_area_id, file_names = self._stage_files_to_be_validated()

        validation_event = ValidationEvent(validation_id=self.validation_id,
                                           job_id=self.job_id,
                                           status="VALIDATING")
        if not test_only:
            update_event(validation_event, {"upload_area_id": upload_area_id, "names": file_names})

        results = self._run_validator()

        results["upload_area_id"] = upload_area_id
        results["names"] = file_names
        validation_event.status = "VALIDATED"

        if not test_only:
            update_event(validation_event, results)

        self._unstage_files()

    @retry(reraise=True,
           stop=stop_after_attempt(5),
           wait=wait_exponential(multiplier=10, min=1, max=4),
           before=before_log(logger, logging.DEBUG),
           before_sleep=before_sleep_log(logger, logging.ERROR))
    def _stage_files_to_be_validated(self):
        upload_area_id = None
        file_names = []
        for s3_file_url in self.s3_file_urls:
            url_bits = parse_url(s3_file_url)
            s3_bucket_name = url_bits.netloc
            s3_object_key = urllib.parse.unquote(url_bits.path.lstrip('/'))
            key_parts = s3_object_key.split('/')
            upload_area_id = key_parts.pop(0)
            file_name = "/".join(key_parts)
            file_names.append(file_name)
            staged_file_path = pathlib.Path(self.staging_folder, s3_object_key)
            self._log("Staging s3://{bucket}/{key} at {file_path}".format(bucket=s3_bucket_name,
                                                                          key=s3_object_key,
                                                                          file_path=staged_file_path))
            staged_file_path.parent.mkdir(parents=True, exist_ok=True)
            self._download_file_from_bucket_to_filesystem(s3_bucket_name, s3_object_key, staged_file_path)
            if not staged_file_path.is_file():
                raise UploadException(status=500, title="Staged file path is not a file",
                                      detail=f"Attempting to stage file path {staged_file_path} failed because it is "
                                      f"not a file.")
            if not staged_file_path.is_file():
                raise TryAgain
            self.staged_file_paths.append(staged_file_path)
        return upload_area_id, file_names

    def _download_file_from_bucket_to_filesystem(self, s3_bucket_name, s3_object_key, staged_file_path):
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(s3_bucket_name)
        bucket.download_file(s3_object_key, str(staged_file_path))

    def _run_validator(self):
        command = [self.path_to_validator]
        for staged_file_path in self.staged_file_paths:
            command.append(str(staged_file_path))
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

    def _unstage_files(self):
        for staged_file_path in self.staged_file_paths:
            self._log("removing file {}".format(staged_file_path))
            staged_file_path.unlink()

    def _find_version(self):
        try:
            with open('/HARNESS_VERSION', 'r') as fp:
                return fp.read().strip()
        except FileNotFoundError:
            return None

    def _log(self, message):
        logger.info("[{id}]: ".format(id=self.job_id) + str(message))
