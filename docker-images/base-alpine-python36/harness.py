#!/usr/bin/env python

import argparse
import json
import logging
import os
import pathlib
import sys
import subprocess
import time
import urllib.parse

import boto3
import pika
from urllib3.util import parse_url


def get_logger(name):
    ch = logging.StreamHandler(sys.stdout)
    log_level_name = os.environ['LOG_LEVEL'] if 'LOG_LEVEL' in os.environ else 'DEBUG'
    log_level = getattr(logging, log_level_name.upper())
    ch.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s',
                                  datefmt="%Y-%m-%dT%H:%M:%S%z")
    ch.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.addHandler(ch)
    logger.setLevel(logging.DEBUG)
    return logger


class ValidatorHarness:

    TIMEOUT = None
    AMQP_EXCHANGE = "ingest.validation.exchange"
    AMQP_ROUTING_KEY = "ingest.file.validation.queue"

    def __init__(self):
        self.version = self._find_version()
        self.validation_id = os.environ['AWS_BATCH_JOB_ID']
        self.logger = get_logger('HARNESS')
        self._log("VERSION {version}, attempt {attempt} with argv: {argv}".format(
            version=self.version, attempt=os.environ['AWS_BATCH_JOB_ATTEMPT'], argv=sys.argv))
        self._parse_args()
        self._stage_file_to_be_validated()
        results = self._run_validator()
        self._unstage_file()
        self._report_results(results)

    def _find_version(self):
        try:
            with open('/HARNESS_VERSION', 'r') as fp:
                return fp.read().strip()
        except FileNotFoundError:
            return None

    def _parse_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('validator', help="Path of validator to invoke")
        parser.add_argument('-t', '--test', action='store_true', help="Test only, do not submit results to Ingest")
        parser.add_argument('-k', '--keep', action='store_true', help="Keep downloaded files after validation")
        parser.add_argument('s3_url', metavar="S3_URL")
        self.args = parser.parse_args()
        self.validator = self.args.validator
        url_bits = parse_url(self.args.s3_url)
        self.bucket_name = url_bits.netloc
        self.s3_object_key = urllib.parse.unquote(url_bits.path.lstrip('/'))

    def _stage_file_to_be_validated(self):
        s3 = boto3.resource('s3')
        self.staged_file_path = os.path.join("/data", self.s3_object_key)
        self._log("Staging s3://{bucket}/{key} at {file_path}".format(bucket=self.bucket_name,
                                                                      key=self.s3_object_key,
                                                                      file_path=self.staged_file_path))
        pathlib.Path(os.path.dirname(self.staged_file_path)).mkdir(parents=True, exist_ok=True)
        s3.Bucket(self.bucket_name).download_file(self.s3_object_key, self.staged_file_path)

    def _run_validator(self):
        command = [self.validator, self.staged_file_path]
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

    def _report_results(self, results):
        self._log("results = {}".format(results))
        if not self.args.test:
            amqp_server = os.environ['INGEST_AMQP_SERVER']
            connection = pika.BlockingConnection(pika.ConnectionParameters(amqp_server))
            channel = connection.channel()
            channel.queue_declare(queue='ingest.file.create.staged')
            result = channel.basic_publish(exchange=self.AMQP_EXCHANGE,
                                           routing_key=self.AMQP_ROUTING_KEY,
                                           body=json.dumps(results))
            self._log("publishing results to {server} returned {result}".format(server=amqp_server, result=result))
            connection.close()

    def _unstage_file(self):
        self._log("removing file {}".format(self.staged_file_path))
        os.remove(self.staged_file_path)

    def _log(self, message):
        self.logger.info("[{id}]: ".format(id=self.validation_id) + str(message))


if __name__ == '__main__':
    ValidatorHarness()
