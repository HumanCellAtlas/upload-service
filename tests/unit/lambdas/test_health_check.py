import datetime
import json
from botocore.stub import Stubber

from dateutil.tz import tzutc
from mock import patch, Mock

from tests.unit import UploadTestCaseUsingMockAWS
from upload.lambdas.health_check.health_check import HealthCheck


class TestHealthCheckDaemon(UploadTestCaseUsingMockAWS):
    def setUp(self):
        super().setUp()
        # Environment
        self.environment = {
            'DEPLOYMENT_STAGE': 'test'
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.health_check = HealthCheck()

    @patch('upload.lambdas.health_check.health_check.HealthCheck.generate_upload_area_status')
    @patch('upload.lambdas.health_check.health_check.HealthCheck.generate_deadletter_queue_status')
    @patch('upload.lambdas.health_check.health_check.HealthCheck.generate_lambda_error_status')
    @patch('upload.lambdas.health_check.health_check.HealthCheck.post_message_to_url')
    def test_health_check_calls_health_functions_and_posts_to_slack(self,
                                                                    mock_post_message_to_url,
                                                                    mock_generate_lambda_error_status,
                                                                    mock_generate_deadletter_queue_status,
                                                                    mock_generate_upload_area_status
                                                                    ):
        mock_generate_upload_area_status.return_value = f"UPLOAD_AREAS: 5 undeleted areas, 4 stuck in checksumming, " \
                                                        f"3 stuck in validation \n2 areas scheduled for checksumming," \
                                                        f" 1 areas scheduled for validation (for over 2 hours)\n"

        mock_generate_lambda_error_status.return_value = f"LAMBDA_ERRORS: 10 for Upload API, 5 for csum daemon"
        mock_generate_deadletter_queue_status.return_value = f"DEADLETTER_QUEUE: 2 in queue, 3 added in past 24 hrs\n"

        self.health_check.run_upload_service_health_check()

        mock_attachment = {
            'attachments': [{
                'title': 'Health Check Report for test:',
                'color': 'good',
                'text': 'DEADLETTER_QUEUE: 2 in queue, 3 added in past 24 hrs\nUPLOAD_AREAS: '
                '5 undeleted areas, 4 stuck in checksumming, 3 stuck in validation \n2 areas'
                ' scheduled for checksumming, 1 areas scheduled for validation (for over 2'
                ' hours)\nLAMBDA_ERRORS: 10 for Upload API, 5 for csum daemon'
            }]
        }
        mock_generate_lambda_error_status.assert_called_once()
        mock_generate_deadletter_queue_status.assert_called_once()
        mock_generate_upload_area_status.assert_called_once()

        mock_post_message_to_url.assert_called_once_with(self.upload_config.slack_webhook, mock_attachment)

    @patch('upload.lambdas.health_check.health_check.requests.post')
    def test_post_message_to_url_calls_request_with_correct_args(self, mock_post_request):
        self.health_check.post_message_to_url('url', 'message')
        headers = {'Content-Type': 'application/json'}
        mock_post_request.assert_called_once_with(url='url', data=json.dumps('message'), headers=headers)

    @patch('upload.lambdas.health_check.health_check.HealthCheck._query_cloudwatch_metrics_for_past_day')
    def test_gen_deadletter_queue_status_queries_cloudwatch_and_formats_string(self, mock_query):
        mock_query.return_value = {'visible_messages': 5, 'received_messages': 2}
        queue_status = self.health_check.generate_deadletter_queue_status()
        expected_deadletter_query = [
            {
                'Id': 'visible_messages',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/SQS',
                        'MetricName': 'ApproximateNumberOfMessagesVisible',
                        'Dimensions': [
                            {
                                'Name': 'QueueName',
                                'Value': f'dcp-upload-pre-csum-deadletter-queue-test'
                            }
                        ]
                    },
                    'Period': 90000,
                    'Stat': 'Average'
                }
            },
            {
                'Id': 'recieved_messages',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/SQS',
                        'MetricName': 'NumberOfMessagesReceived',
                        'Dimensions': [
                            {
                                'Name': 'QueueName',
                                'Value': f'dcp-upload-pre-csum-deadletter-queue-test'
                            }
                        ]
                    },
                    'Period': 90000,
                    'Stat': 'Average'
                }
            }
        ]
        assert mock_query.called_once_with(expected_deadletter_query)
        assert queue_status == 'DEADLETTER_QUEUE: 5 in queue, 2 added in past 24 hrs\n'

    @patch('upload.lambdas.health_check.health_check.HealthCheck._query_cloudwatch_metrics_for_past_day')
    def test_gen_lambda_error_status_queries_cloudwatch_and_formats_string(self, mock_query):
        mock_query.return_value = {'upload_api_lambda_errors': 5, 'checksum_daemon_lambda_errors': 2}
        lambada_status = self.health_check.generate_lambda_error_status()
        expected_lambda_error_query = [
            {
                'Id': 'upload_api_lambda_errors',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/Lambda',
                        'MetricName': 'Errors',
                        'Dimensions': [
                            {
                                'Name': 'FunctionName',
                                'Value': f'upload-api-test'
                            }
                        ]
                    },
                    'Period': 90000,
                    'Stat': 'Sum'
                }
            },
            {
                'Id': 'checksum_daemon_lambda_errors',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/Lambda',
                        'MetricName': 'Errors',
                        'Dimensions': [
                            {
                                'Name': 'FunctionName',
                                'Value': f'dcp-upload-csum-test'
                            }
                        ]
                    },
                    'Period': 90000,
                    'Stat': 'Sum'
                }
            }
        ]
        mock_query.called_once_with(expected_lambda_error_query)
        assert lambada_status == "LAMBDA_ERRORS: 5 for Upload API, 2 for csum daemon"

    @patch('upload.lambdas.health_check.health_check.HealthCheck._query_db_and_return_first_row')
    def test_gen_upload_area_status_queries_db_and_formats_string(self, mock_query_db):
        mock_query_db.side_effect = [5, 4, 3, 2, 1]
        upload_area_status = self.health_check.generate_upload_area_status()
        assert mock_query_db.call_count == 5

        assert upload_area_status == "UPLOAD_AREAS: 5 undeleted areas, 4 stuck in checksumming, 3 stuck in " \
                                     "validation \n2 files scheduled for checksumming, 1 files scheduled for " \
                                     "validation (for over 2 hours)\n"

    @patch('upload.lambdas.health_check.health_check.datetime')
    def test_query_cloudwatch_metrics_calls_boto3_client(self, mock_datetime):
        endtime = datetime.datetime(2018, 10, 8, 23, 12, 48, 663351)
        starttime = datetime.datetime(2018, 10, 7, 23, 12, 48, 663351)
        mock_datetime.utcnow = Mock(return_value=endtime)
        expected_deadletter_query = [
            {
                'Id': 'visible_messages',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/SQS',
                        'MetricName': 'ApproximateNumberOfMessagesVisible',
                        'Dimensions': [
                            {
                                'Name': 'QueueName',
                                'Value': f'dcp-upload-pre-csum-deadletter-queue-test'
                            }
                        ]
                    },
                    'Period': 90000,
                    'Stat': 'Average'
                }
            },
            {
                'Id': 'recieved_messages',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/SQS',
                        'MetricName': 'NumberOfMessagesReceived',
                        'Dimensions': [
                            {
                                'Name': 'QueueName',
                                'Value': f'dcp-upload-pre-csum-deadletter-queue-test'
                            }
                        ]
                    },
                    'Period': 90000,
                    'Stat': 'Average'
                }
            }
        ]
        mock_deadletter_metric_data = {
            'MetricDataResults': [{'Id': 'visible_messages',
                                   'Label': 'ApproximateNumberOfMessagesVisible',
                                   'Timestamps': [
                                       datetime.datetime(2018, 10, 4, 23, 32, tzinfo=tzutc())],
                                   'Values': [10.0],
                                   'StatusCode': 'Complete'},
                                  {'Id': 'received_messages',
                                   'Label': 'NumberOfMessagesReceived',
                                   'Timestamps': [
                                       datetime.datetime(2018, 10, 4, 23, 32, tzinfo=tzutc())],
                                   'Values': [3.0],
                                   'StatusCode': 'Complete'}],
            'ResponseMetadata': {'RequestId': '1506bb49-c8f7-11e8-b5b9-5135a8265cdd',
                                 'HTTPStatusCode': 200,
                                 'HTTPHeaders': {
                                     'x-amzn-requestid': '1506bb49-c8f7-11e8-b5b9-5135a8265cdd',
                                     'content-type': 'text/xml',
                                     'content-length': '945',
                                     'date': 'Fri, 05 Oct 2018 23:33:36 GMT'},
                                 'RetryAttempts': 0}
        }
        from upload.lambdas.health_check.health_check import client

        stubber = Stubber(client)
        stubber.add_response('get_metric_data', mock_deadletter_metric_data, {
            'MetricDataQueries': expected_deadletter_query, 'StartTime': starttime, 'EndTime': endtime
        })
        stubber.activate()

        deadletter_dict = self.health_check._query_cloudwatch_metrics_for_past_day(expected_deadletter_query)

        assert deadletter_dict == {'visible_messages': 10, 'received_messages': 3}
        stubber.deactivate()

    @patch('upload.lambdas.health_check.health_check.datetime')
    def test_query_cloudwatch_handles_empty_return_values(self, mock_datetime):
        endtime = datetime.datetime(2018, 10, 8, 23, 12, 48, 663351)
        starttime = datetime.datetime(2018, 10, 7, 23, 12, 48, 663351)
        mock_datetime.utcnow = Mock(return_value=endtime)
        expected_deadletter_query = [
            {
                'Id': 'visible_messages',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/SQS',
                        'MetricName': 'ApproximateNumberOfMessagesVisible',
                        'Dimensions': [
                            {
                                'Name': 'QueueName',
                                'Value': f'dcp-upload-pre-csum-deadletter-queue-test'
                            }
                        ]
                    },
                    'Period': 90000,
                    'Stat': 'Average'
                }
            },
            {
                'Id': 'received_messages',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/SQS',
                        'MetricName': 'NumberOfMessagesReceived',
                        'Dimensions': [
                            {
                                'Name': 'QueueName',
                                'Value': f'dcp-upload-pre-csum-deadletter-queue-test'
                            }
                        ]
                    },
                    'Period': 90000,
                    'Stat': 'Average'
                }
            }
        ]
        mock_deadletter_metric_data = {
            'MetricDataResults': [{'Id': 'visible_messages',
                                   'Label': 'ApproximateNumberOfMessagesVisible',
                                   'Timestamps': [
                                       datetime.datetime(2018, 10, 4, 23, 32, tzinfo=tzutc())],
                                   'Values': [],
                                   'StatusCode': 'Complete'},
                                  {'Id': 'received_messages',
                                   'Label': 'NumberOfMessagesReceived',
                                   'Timestamps': [
                                       datetime.datetime(2018, 10, 4, 23, 32, tzinfo=tzutc())],
                                   'Values': [],
                                   'StatusCode': 'Complete'}],
            'ResponseMetadata': {'RequestId': '1506bb49-c8f7-11e8-b5b9-5135a8265cdd',
                                 'HTTPStatusCode': 200,
                                 'HTTPHeaders': {
                                     'x-amzn-requestid': '1506bb49-c8f7-11e8-b5b9-5135a8265cdd',
                                     'content-type': 'text/xml',
                                     'content-length': '945',
                                     'date': 'Fri, 05 Oct 2018 23:33:36 GMT'},
                                 'RetryAttempts': 0}
        }
        from upload.lambdas.health_check.health_check import client

        stubber = Stubber(client)
        stubber.add_response('get_metric_data', mock_deadletter_metric_data, {
            'MetricDataQueries': expected_deadletter_query, 'StartTime': starttime, 'EndTime': endtime
        })
        stubber.activate()

        deadletter_dict = self.health_check._query_cloudwatch_metrics_for_past_day(expected_deadletter_query)

        assert deadletter_dict == {'visible_messages': 'no value returned', 'received_messages': 'no value returned'}
        stubber.deactivate()

    @patch('upload.lambdas.health_check.health_check._run_query')
    def test_query_db_and_return_first_row_queries_db_and_handles_expected_db_response(self, mock_run_query):
        mock_run_query.return_value = MockIt()
        area_count = self.health_check._query_db_and_return_first_row("SELECT COUNT(*) FROM checksum ")

        assert area_count == 1
        mock_run_query.assert_called_once_with("SELECT COUNT(*) FROM checksum ")


class MockIt:
    def fetchall(self):
        return [[1]]
