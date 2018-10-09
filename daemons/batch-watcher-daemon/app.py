import os

import boto3
import requests

from upload.common.database import run_query, run_query_with_params
from upload.common.retry import retry_on_aws_too_many_requests

api_key = os.environ["INGEST_API_KEY"]
deployment_stage = os.environ["DEPLOYMENT_STAGE"]
batch_client = boto3.client("batch")
ec2_client = boto3.client('ec2')


def batch_watcher_handler(event=None, context=None):
    query_results = run_query("SELECT * from validation WHERE status = 'SCHEDULED' or status = 'VALIDATING';")
    rows = query_results.fetchall()
    kill_instances = True
    for row in rows:
        job_id = row["job_id"]
        response = batch_client.describe_jobs(jobs=[job_id])["jobs"][0]
        if response["status"] == "FAILED":
            kill_instances = True
            break

    if kill_instances:
        find_and_kill_deployment_batch_instances()
        for row in rows:
            db_id = row["id"]
            old_job_id = row["job_id"]
            file_id = row["file_id"]
            file_id_split = file_id.split("/")
            upload_area_id = file_id_split[0]
            file_name = file_id_split[1]
            run_query_with_params("UPDATE validation SET status = 'FAILED' \
                WHERE id = %s;", db_id)
            new_job_id = schedule_validation_job(upload_area_id, file_name)
            run_query_with_params("UPDATE validation SET original_attempt_job_id = %s \
                WHERE job_id = %s;", (old_job_id, new_job_id))


def find_and_kill_deployment_batch_instances():
    instance_ids = []
    key_name = f"hca-upload-{deployment_stage}"
    reservations = ec2_client.describe_instances(
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
        ec2_client.terminate_instances(InstanceIds=instance_ids)


def schedule_validation_job(upload_area_id, file_name):
    upload_url = "https://upload.{0}.data.humancellatlas.org/v1/area/{1}/{2}/validate".format(deployment_stage, upload_area_id, file_name)
    headers = {'Api-Key': api_key}
    message = {"validator_image": "quay.io/humancellatlas/fastq_utils:master"}
    response = requests.put(upload_url, headers=headers, json=message)
    response_json = response.json()
    if response.status_code == requests.codes.ok:
        new_job_id = response_json["validation_id"]
        print("scheduled {0}/{1} for validation with new job id of {2}".format(upload_area_id, file_name, new_job_id))
        return new_job_id
    else:
        raise UploadException("Failed to schedule {0}/{1} for validation".format(upload_area_id, file_name))

batch_watcher_handler()
