import json

from botocore.stub import Stubber
from mock import patch, Mock

from upload.lambdas.batch_watcher.batch_watcher import BatchWatcher
from tests.unit import UploadTestCaseUsingMockAWS, EnvironmentSetup
from upload.common.checksum_event import UploadedFileChecksumEvent
from upload.common.validation_event import UploadedFileValidationEvent


class TestBatchWatcherDaemon(UploadTestCaseUsingMockAWS):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setUp(self):
        super().setUp()
        self.environment = {
            'DEPLOYMENT_STAGE': 'test',
            'API_KEY': 'test'
        }
        EnvironmentSetup(self.environment)
        self.batch_watcher = BatchWatcher()
        self.mock_batch_client = Stubber(self.batch_watcher.batch_client)
        self.mock_ec2_client = Stubber(self.batch_watcher.ec2_client)
        self.mock_lambda_client = Stubber(self.batch_watcher.lambda_client)

    @patch('upload.lambdas.batch_watcher.batch_watcher.run_query')
    def test_find_incomplete_batch_jobs(self, mock_run_query):
        mock_run_query.return_value = QueryResult()
        csum_jobs, val_jobs = self.batch_watcher.find_incomplete_batch_jobs()
        self.assertEqual(csum_jobs, [{"id": "123", "job_id": "123", "file_id": "test/test"}])
        self.assertEqual(val_jobs, [{"id": "123", "job_id": "123", "file_id": "test/test"}])

    def test_find_and_kill_deployment_batch_instances(self):
        describe_params = {
            "Filters": [
                {"Name": 'key-name', "Values": ["hca-upload-test"]},
                {"Name": 'instance-state-name', "Values": ["running"]}
            ]
        }
        describe_output = {
            "Reservations": [{
                "Instances": [
                    {
                        "InstanceId": "instance_one"
                    },
                    {
                        "InstanceId": "instance_two"
                    }
                ]
            }]
        }
        instance_ids = ["instance_one", "instance_two"]
        terminate_params = {
            "InstanceIds": instance_ids
        }
        self.mock_ec2_client.add_response("describe_instances", describe_output, describe_params)
        self.mock_ec2_client.add_response("terminate_instances", {}, terminate_params)
        self.mock_ec2_client.activate()
        killed_instance_ids = self.batch_watcher.find_and_kill_deployment_batch_instances()
        self.assertEqual(killed_instance_ids, instance_ids)

    @patch('upload.lambdas.batch_watcher.batch_watcher.run_query_with_params')
    @patch('upload.lambdas.batch_watcher.batch_watcher.BatchWatcher.schedule_validation_job')
    def test_schedule_job_with_validation(self, mock_schedule_validation_job, mock_run_query):
        row = {
            "id": "123",
            "file_id": "test_area/test_id",
            "job_id": "124"
        }
        self.batch_watcher.schedule_job(row, "validation")
        mock_schedule_validation_job.assert_called_with("test_area", "test_id")

    @patch('upload.lambdas.batch_watcher.batch_watcher.run_query_with_params')
    @patch('upload.lambdas.batch_watcher.batch_watcher.BatchWatcher.invoke_checksum_lambda')
    def test_schedule_job_with_checksum(self, mock_invoke_csum_lambda, mock_run_query):
        row = {
            "id": "123",
            "file_id": "test_area/test_id",
            "job_id": "124"
        }
        self.batch_watcher.schedule_job(row, "checksum")
        mock_invoke_csum_lambda.assert_called_with("test_area/test_id")

    def test_invoke_checksum_lambda(self):
        payload = {
            'Records': [{
                'eventName': 'ObjectCreated:Put',
                "s3": {
                    "bucket": {
                        "name": f"org-humancellatlas-upload-test"
                    },
                    "object": {
                        "key": "test_area/test_file_id"
                    }
                }
            }]
        }
        lambda_params = {
            "FunctionName": f"dcp-upload-csum-test",
            "InvocationType": "Event",
            "Payload": json.dumps(payload).encode()
        }
        self.mock_lambda_client.add_response('invoke', {}, lambda_params)
        self.mock_lambda_client.activate()
        self.batch_watcher.invoke_checksum_lambda("test_area/test_file_id")
        self.mock_lambda_client.deactivate()

    def test_should_instances_be_killed_true(self):
        test_one_rows = [
            {
                "id": "123",
                "file_id": "test/test",
                "job_id": "124"
            },
            {
                "id": "234",
                "file_id": "test/test",
                "job_id": "235"
            }
        ]
        output_one = {
            "jobs": [{
                "status": "FAILED",
                "jobName": "test",
                "jobId": "test",
                "jobQueue": "test",
                "startedAt": 1234,
                "jobDefinition": "test"
            }]
        }
        output_two = {
            "jobs": [{
                "status": "SUCCEEDED",
                "jobName": "test",
                "jobId": "test",
                "jobQueue": "test",
                "startedAt": 1234,
                "jobDefinition": "test"
            }]
        }
        self.mock_batch_client.add_response('describe_jobs', output_one, {"jobs": ["124"]})
        self.mock_batch_client.add_response('describe_jobs', output_two, {"jobs": ["235"]})
        self.mock_batch_client.activate()

        kill_instances = self.batch_watcher.should_instances_be_killed(test_one_rows)
        self.assertEqual(kill_instances, True)
        self.mock_batch_client.deactivate()

    def test_should_instances_be_killed_false(self):
        test_rows = [
            {
                "id": "345",
                "file_id": "test/test",
                "job_id": "346"
            },
            {
                "id": "456",
                "file_id": "test/test",
                "job_id": "457"
            }
        ]
        output_two = {
            "jobs": [{
                "status": "SUCCEEDED",
                "jobName": "test",
                "jobId": "test",
                "jobQueue": "test",
                "startedAt": 1234,
                "jobDefinition": "test"
            }]
        }
        self.mock_batch_client.add_response('describe_jobs', output_two, {"jobs": ["346"]})
        self.mock_batch_client.add_response('describe_jobs', output_two, {"jobs": ["457"]})
        self.mock_batch_client.activate()
        kill_instances = self.batch_watcher.should_instances_be_killed(test_rows)
        self.assertEqual(kill_instances, False)
        self.mock_batch_client.deactivate()


class QueryResult:
    def fetchall(self):
        return [{"id": "123", "job_id": "123", "file_id": "test/test"}]
