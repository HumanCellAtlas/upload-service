from datetime import datetime

import boto3
from botocore.errorfactory import ClientError


class BatchJobDumper:

    def __init__(self):
        self.batch = boto3.client('batch')
        self.logs = boto3.client('logs')

    def describe_job(self, job_id):
        response = self.batch.describe_jobs(jobs=[job_id])
        for job in response['jobs']:

            try:
                print(f"Job Name           {job['jobName']}")
                print(f"Job Id             {job['jobId']}")
                print(f"Job Queue          {job['jobQueue']}")
                print(f"Job Definition     {job['jobDefinition']}")
                print(f"Status             {job['status']}")
                print(f"Status Reason      {job['statusReason']}")
                print(f"Created at         {self._datetime(job, 'createdAt')}")
                print(f"Started at         {self._datetime(job, 'startedAt')}")
                print(f"Stopped at         {self._datetime(job, 'stoppedAt')}")
                if 'startedAt' in job and 'stoppedAt' in job:
                    print(f"Duration           {(job['stoppedAt'] - job['startedAt'])/1000}s")
                print(f"Container:")
                print(f"\tImage    {job['container']['image']}")
                print(f"\tIvCPUs   {job['container']['vcpus']}")
                print(f"\tMemory   {job['container']['memory']}")
                print(f"\tCommand  {' '.join(job['container']['command'])}")
                print(f"\tReason   {job['container']['reason']}")
                if 'attempts' in job:
                    print("Attempts:")
                    for idx, attempt in enumerate(job['attempts']):
                        print(f"\tAttempt #{idx}")
                        print(f"\tStopped At:    {self._datetime(attempt, 'stoppedAt')}")
                        print(f"\tStatus Reason: {attempt['statusReason']}")
                        print(f"\tContainer:")
                        print(f"\t\tContainer Reason   {attempt['container']['reason']}")
                        print("")
            except KeyError:
                pass
            print("Log:")
            if 'logStreamName' in job['container']:
                self._display_log('/aws/batch/job', job['container']['logStreamName'])
            else:
                print("No log yet.")

    def _display_log(self, log_group_name, log_stream_name):
        try:
            for event in self.logs.get_log_events(logGroupName=log_group_name, logStreamName=log_stream_name)['events']:
                print("  " + event['message'])
        except ClientError:
            pass

    @staticmethod
    def _datetime(dictionary, key):
        if key in dictionary and dictionary[key]:
            return datetime.fromtimestamp(dictionary[key]/1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            return ""
