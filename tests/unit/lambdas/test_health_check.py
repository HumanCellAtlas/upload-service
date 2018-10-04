import datetime
import json

from dateutil.tz import tzutc
from mock import patch, Mock
from botocore.stub import Stubber

from tests.unit import UploadTestCaseUsingMockAWS, EnvironmentSetup
from upload.lambdas.health_check.health_check import HealthCheck


class TestHealthCheckDaemon(UploadTestCaseUsingMockAWS):
    def setUp(self):
        super().setUp()
        # Environment
        # self.environment = {
        #     'DEPLOYMENT_STAGE': 'test'
        # }
        self.environmentor = EnvironmentSetup(self.environment)
        self.health_check = HealthCheck()

    def tearDown(self):
        super().tearDown()
        self.environmentor.exit()

    def test_health_check_cron_job(self):
        pass

    @patch('upload.lambdas.health_check.health_check.HealthCheck.get_deadletter_count')
    @patch('upload.lambdas.health_check.health_check.HealthCheck.parse_and_query_db')
    @patch('upload.lambdas.health_check.health_check.HealthCheck.post_message_to_url')
    def test_health_check_calls_health_functions_and_posts_to_slack(self,
                                                                    mock_post_message_to_url,
                                                                    mock_parse_and_query_db,
                                                                    mock_get_deadletter_count
                                                                    ):
        mock_parse_and_query_db.return_value = 2
        mock_get_deadletter_count.return_value = {'ApproximateNumberOfMessagesVisible': 5,
                                                  'NumberOfMessagesReceived': 3}
        webhook = 'https://hooks.slack.com/services/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'
        mock_attachment = {'attachments': [
            {'title': 'Health Check Report for test:',
             'color': 'good',
             'text': 'DEADLETTER QUEUE: 5 in queue, 3 added in past 24 hrs\nUPLOAD_AREAS: 2 undeleted areas, 2 stuck '
                     'in checksumming, 2 stuck in validation'
             }]
        }
        self.health_check.health_check()
        mock_get_deadletter_count.assert_called_once()
        assert mock_parse_and_query_db.call_count == 3
        mock_post_message_to_url.assert_called_once_with(webhook, mock_attachment)

    @patch('upload.lambdas.health_check.health_check.requests.post')
    def test_post_message_to_url_calls_request_with_correct_args(self, mock_post_request):
        self.health_check.post_message_to_url('url', 'message')
        headers = {'Content-Type': 'application/json'}
        mock_post_request.assert_called_once_with(url='url', data=json.dumps('message'), headers=headers)

    @patch('upload.lambdas.health_check.health_check.datetime')
    def test_get_deadletter_count_formats_queue_name_and_calls_boto3_client(self, mock_datetime):
        endtime = datetime.datetime(2018, 10, 8, 23, 12, 48, 663351)
        starttime = datetime.datetime(2018, 10, 7, 23, 12, 48, 663351)
        mock_datetime.utcnow = Mock(return_value=endtime)

        expected_metric_data_queries = [
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
        mock_metric_data = {
            'MetricDataResults': [{'Id': 'visible_messages',
                                   'Label': 'ApproximateNumberOfMessagesVisible',
                                   'Timestamps': [
                                       datetime.datetime(2018, 10, 4, 23, 32, tzinfo=tzutc())],
                                   'Values': [10.0],
                                   'StatusCode': 'Complete'},
                                  {'Id': 'recieved_messages',
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
        stubber.add_response('get_metric_data', mock_metric_data, {'MetricDataQueries': expected_metric_data_queries,
                                                                   'StartTime': starttime, 'EndTime': endtime})
        stubber.activate()

        deadletter_dict = HealthCheck().get_deadletter_count()
        assert deadletter_dict == {'ApproximateNumberOfMessagesVisible': 10, 'NumberOfMessagesReceived': 3}

    @patch('upload.lambdas.health_check.health_check._run_query')
    def test_get_undeleted_upload_area_count_handles_expected_db_response(self, mock_run_query):
        mock_run_query.return_value = MockIt()
        area_count = self.health_check.parse_and_query_db("SELECT COUNT(*) FROM checksum ")

        assert area_count == 1
        mock_run_query.assert_called_once_with("SELECT COUNT(*) FROM checksum ")


class MockIt():
    def fetchall(self):
        return [[1]]
