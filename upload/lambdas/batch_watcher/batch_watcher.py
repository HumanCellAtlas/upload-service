import os
import json

import boto3
import requests

from upload.common.retry import retry_on_aws_too_many_requests
from upload.common.logging import get_logger
from upload.common.database import run_query, run_query_with_params
from upload.common.exceptions import UploadException

logger = get_logger(__name__)


class BatchWatcher:
    def __init__(self):
        self.api_key = os.environ["INGEST_API_KEY"]
        self.deployment_stage = os.environ["DEPLOYMENT_STAGE"]
        self.api_host = os.environ["API_HOST"]
        self.batch_client = boto3.client("batch")
        self.ec2_client = boto3.client('ec2')
        self.lambda_client = boto3.client('lambda')

    def run(self):
        incomplete_checksum_jobs, incomplete_validation_jobs = self.find_incomplete_batch_jobs()
        logger.info(f"Found {len(incomplete_checksum_jobs)} incomplete checksum jobs utilizing batch")
        logger.info(f"Found {len(incomplete_validation_jobs)} incomplete validation jobs utilizing batch")
        incomplete_jobs = incomplete_checksum_jobs + incomplete_validation_jobs
        kill_instances = self.should_instances_be_killed(incomplete_jobs)
        if kill_instances:
            self.find_and_kill_deployment_batch_instances()
            # Re fetch incomplete checksum and validation jobs after killing instances to catch newly scheduled
            incomplete_checksum_jobs, incomplete_validation_jobs = self.find_incomplete_batch_jobs()
            for row in incomplete_validation_jobs:
                self.schedule_job(row, "validation")
            for row in incomplete_checksum_jobs:
                self.schedule_job(row, "checksum")
            logger.info(f"Finished rescheduling {len(incomplete_validation_jobs)} validation jobs and \
                {len(incomplete_checksum_jobs)} checksum jobs")
        else:
            logger.info("No new failed jobs detected in batch. Jobs will continue untouched.")

    def should_instances_be_killed(self, rows):
        kill_instances = False
        for row in rows:
            db_id = row["id"]
            job_id = row["job_id"]
            file_id = row["file_id"]
            status = self._get_job_status(job_id)
            if status == "FAILED":
                logger.info(f"database record id {db_id} for file {file_id} represents a failed batch job. \
                    Time to kill instances.")
                kill_instances = True
                break
        return kill_instances

    @retry_on_aws_too_many_requests
    def _get_job_status(self, job_id):
        response = self.batch_client.describe_jobs(jobs=[job_id])
        jobs = response.get("jobs")
        if jobs and len(jobs):
            status = jobs[0]["status"]
            return status

    def find_incomplete_batch_jobs(self):
        validation_results = run_query("SELECT * from validation WHERE status = 'SCHEDULED' or status = 'VALIDATING';")
        validation_rows = validation_results.fetchall()
        checksum_results = run_query("SELECT * from checksum WHERE(status='SCHEDULED' or status = 'CHECKSUMMING') \
            and job_id is not null;")
        checksum_rows = checksum_results.fetchall()
        return checksum_rows, validation_rows

    def find_and_kill_deployment_batch_instances(self):
        instance_ids = []
        key_name = f"hca-upload-{self.deployment_stage}"
        reservations = self.ec2_client.describe_instances(
            Filters=[
                {'Name': 'key-name',
                 'Values': [key_name]},
                {'Name': 'instance-state-name',
                 'Values': ["running"]}
            ])

        instance_groups = [x["Instances"] for x in reservations["Reservations"]]
        for group in instance_groups:
            for instance in group:
                instance_ids.append(instance['InstanceId'])
        if len(instance_ids):
            logger.info(f"Killing instances associated with key {key_name} and ec2 ids {str(instance_ids)}")
            self.ec2_client.terminate_instances(InstanceIds=instance_ids)
        return instance_ids

    def schedule_job(self, row, table_name):
        db_id = row["id"]
        file_id = row["file_id"]
        file_id_split = file_id.split("/")
        upload_area_id = file_id_split[0]
        file_name = file_id_split[1]
        if table_name == "checksum":
            self.invoke_checksum_lambda(file_id)
        elif table_name == "validation":
            docker_image = row["docker_image"]
            # Multiple validation attempts on a file should point to the same original validation id
            original_validation_id = row["original_validation_id"]
            if not original_validation_id:
                # If there is no original_validation_id,
                # set the db id of first validation attempt as original_validation_id.
                original_validation_id = db_id
            self.schedule_validation_job(upload_area_id, file_name, docker_image, original_validation_id)
        logger.info(f"Marking {table_name} record id {db_id} for file {file_id} as failed.")
        run_query_with_params(f"UPDATE {table_name} SET status = 'FAILED' \
            WHERE id = %s;", (db_id))

    def schedule_validation_job(self, upload_area_id, file_name, docker_image, original_validation_id):
        headers = {'Api-Key': self.api_key}
        message = {
            "validator_image": docker_image,
            "original_validation_id": original_validation_id
        }
        response = requests.put(self.api_host, headers=headers, json=message)
        if response.status_code == requests.codes.ok:
            logger.info(f"scheduled {upload_area_id}/{file_name} for validation")
        else:
            raise UploadException(f"Failed to schedule {upload_area_id}/{file_name} for validation")

    def invoke_checksum_lambda(self, file_id):
        payload = {
            'Records': [{
                'eventName': 'ObjectCreated:Put',
                "s3": {
                    "bucket": {
                        "name": f"org-humancellatlas-upload-{self.deployment_stage}"
                    },
                    "object": {
                        "key": file_id
                    }
                }
            }]
        }
        self.lambda_client.invoke(
            FunctionName=f"dcp-upload-csum-{self.deployment_stage}",
            InvocationType='Event',
            Payload=json.dumps(payload).encode()
        )
        logger.info(f"scheduled {file_id} for checksumming")
