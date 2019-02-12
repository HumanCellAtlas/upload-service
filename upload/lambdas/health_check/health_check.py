import json
import logging
import os
from datetime import datetime, timedelta

import boto3
import requests

from upload.common.database import UploadDB
from upload.common.upload_config import UploadConfig

logger = logging.getLogger(__name__)

client = boto3.client('cloudwatch')


class HealthCheck:
    def __init__(self):
        self.env = os.environ['DEPLOYMENT_STAGE']
        self.db = UploadDB()
        logger.debug(f"Running a health check for {self.env}. Results will be posted in #upload-service")
        self.webhook = UploadConfig().slack_webhook

        self.stale_checksum_job_count_query = "SELECT COUNT(*) FROM checksum " \
                                              "WHERE status='CHECKSUMMING' " \
                                              "AND created_at > CURRENT_DATE - interval '4 weeks' " \
                                              "AND updated_at > CURRENT_TIMESTAMP - interval '2 hours'"
        self.stale_validation_job_count_query = "SELECT COUNT(*) FROM validation " \
                                                "WHERE status='VALIDATING' " \
                                                "AND created_at > CURRENT_DATE - interval '4 weeks' " \
                                                "AND updated_at > CURRENT_TIMESTAMP - interval '2 hours'"
        self.scheduled_checksum_job_count_query = "SELECT COUNT(*) FROM checksum " \
                                                  "WHERE status='SCHEDULED' " \
                                                  "AND created_at > CURRENT_DATE - interval '4 weeks' " \
                                                  "AND updated_at > CURRENT_TIMESTAMP - interval '2 hours'"
        self.scheduled_validation_job_count_query = "SELECT COUNT(*) FROM validation " \
                                                    "WHERE status='SCHEDULED' " \
                                                    "AND created_at > CURRENT_DATE - interval '4 weeks' " \
                                                    "AND updated_at > CURRENT_TIMESTAMP - interval '2 hours'"
        self.undeleted_areas_count_query = "SELECT COUNT(*) FROM upload_area " \
                                           "WHERE created_at > CURRENT_DATE - interval '4 weeks' " \
                                           "AND status != 'DELETED'"
        self.failed_checksum_count_query = "SELECT COUNT(*) FROM checksum " \
                                           "WHERE status='FAILED' " \
                                           "AND updated_at >= NOW() - '1 day'::INTERVAL"
        self.failed_validation_count_query = "SELECT COUNT(*) FROM validation " \
                                             "WHERE status='FAILED' " \
                                             "AND updated_at >= NOW() - '1 day'::INTERVAL"
        self.deadletter_metric_queries = [
            {
                'Id': 'visible_messages',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/SQS',
                        'MetricName': 'ApproximateNumberOfMessagesVisible',
                        'Dimensions': [
                            {
                                'Name': 'QueueName',
                                'Value': f'dcp-upload-pre-csum-deadletter-queue-{self.env}'
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
                                'Value': f'dcp-upload-pre-csum-deadletter-queue-{self.env}'
                            }
                        ]
                    },
                    'Period': 90000,
                    'Stat': 'Average'
                }
            }
        ]
        self.lambda_error_queries = [
            {
                'Id': 'upload_api_lambda_errors',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/Lambda',
                        'MetricName': 'Errors',
                        'Dimensions': [
                            {
                                'Name': 'FunctionName',
                                'Value': f'upload-api-{self.env}'
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
                                'Value': f'dcp-upload-csum-{self.env}'
                            }
                        ]
                    },
                    'Period': 90000,
                    'Stat': 'Sum'
                }
            }
        ]

    def run_upload_service_health_check(self):
        deadletter_queue_info = self.generate_deadletter_queue_status()
        upload_area_info = self.generate_upload_area_status()
        lambda_info = self.generate_lambda_error_status()

        if deadletter_queue_info == upload_area_info == lambda_info == 'GOOD\n':
            color = 'good'
            status_info = "It's 6 o'clock somewhere and all is well"
        else:
            color = 'bad'
            status_info = (
                f"DEADLETTER_QUEUE: {deadletter_queue_info}" +
                f"UPLOAD_AREAS: {upload_area_info}" +
                f"LAMBDAS: {lambda_info}"
            )

        attachments = [{
            "title": f"Health Check Report for {self.env}:",
            "color": color,
            "text": status_info
        }]

        self.post_message_to_url(self.webhook, {"attachments": attachments})

    def generate_deadletter_queue_status(self):
        deadletter_results = self._query_cloudwatch_metrics_for_past_day(self.deadletter_metric_queries)
        if deadletter_results['received_messages'] == 0:
            deadletter_queue_status = "GOOD\n"
        else:
            deadletter_queue_status = f"{deadletter_results['visible_messages']} in queue, " \
                f"{deadletter_results['received_messages']} added in past 24 hrs\n"
        return deadletter_queue_status

    def generate_lambda_error_status(self):
        lambda_error_results = self._query_cloudwatch_metrics_for_past_day(self.lambda_error_queries)
        if lambda_error_results['upload_api_lambda_errors'] == 0 and \
                lambda_error_results['checksum_daemon_lambda_errors'] == 0:
            lambda_error_status = 'GOOD\n'
        else:
            lambda_error_status = f"{lambda_error_results['upload_api_lambda_errors']} errors for Upload API, " \
                                  f"{lambda_error_results['checksum_daemon_lambda_errors']} errors for csum daemon\n"
        return lambda_error_status

    def generate_upload_area_status(self):
        undeleted_upload_area_count = self._query_db_and_return_first_row(self.undeleted_areas_count_query)
        stale_checksumming_areas = self._query_db_and_return_first_row(self.stale_checksum_job_count_query)
        stale_validating_areas = self._query_db_and_return_first_row(self.stale_validation_job_count_query)
        scheduled_checksum_areas = self._query_db_and_return_first_row(self.scheduled_checksum_job_count_query)
        scheduled_validation_areas = self._query_db_and_return_first_row(self.scheduled_validation_job_count_query)
        failed_checksum_count = self._query_db_and_return_first_row(self.failed_checksum_count_query)
        failed_validation_count = self._query_db_and_return_first_row(self.failed_validation_count_query)
        if (stale_checksumming_areas + stale_validating_areas + scheduled_checksum_areas + scheduled_validation_areas +
                failed_checksum_count + failed_validation_count) == 0:
            upload_area_status = 'GOOD\n'
        else:
            upload_area_status = f"{undeleted_upload_area_count} undeleted areas, {stale_checksumming_areas}" \
                                 f" stuck in checksumming, {stale_validating_areas} stuck in validation \n" \
                                 f"{scheduled_checksum_areas} files scheduled for checksumming, " \
                                 f"{scheduled_validation_areas} files scheduled for validation (for over 2 hours)\n" \
                                 f"{failed_checksum_count} files failed batch checksumming in last day\n" \
                                 f"{failed_validation_count} files failed batch validation in last day\n"
        return upload_area_status

    def post_message_to_url(self, url, message):
        body = json.dumps(message)
        headers = {'Content-Type': 'application/json'}
        requests.post(url=url, data=body, headers=headers)

    def _query_cloudwatch_metrics_for_past_day(self, metric_data_queries):
        now = datetime.utcnow()
        yesterday = now - timedelta(hours=24)
        response = client.get_metric_data(MetricDataQueries=metric_data_queries, StartTime=yesterday, EndTime=now)
        results = {}
        for info in response['MetricDataResults']:
            if len(info['Values']) > 0:
                results[info['Id']] = int(info['Values'][0])
            else:
                results[info['Id']] = "no value returned"
        return results

    def _query_db_and_return_first_row(self, query):
        query_result = self.db.run_query(query)
        rows = query_result.fetchall()
        if len(rows) > 0:
            results = rows[0][0]
            return results
