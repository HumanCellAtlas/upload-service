from datetime import datetime, timedelta
import json
import os

import boto3
import requests

from upload.common.database import _run_query
from upload.common.logging import get_logger

logger = get_logger(__name__)

client = boto3.client('cloudwatch')


class HealthCheck:
    def __init__(self):
        self.env = os.environ['DEPLOYMENT_STAGE']
        logger.debug(f"Running a health check for {self.env}. Results will be posted in #upload-service")
        self.test_webhook = "https://hooks.slack.com/services/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"
        self.webhook = "https://hooks.slack.com/services/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"
        self.checksumming_areas_count_query = "SELECT COUNT(*) FROM checksum " \
                                              "WHERE status='CHECKSUMMING' " \
                                              "AND created_at > CURRENT_DATE - interval '4 weeks' " \
                                              "AND updated_at > CURRENT_TIMESTAMP - interval '2 hours'"
        self.validation_areas_count_query = "SELECT COUNT(*) FROM validation " \
                                            "WHERE status='VALIDATING' " \
                                            "AND created_at > CURRENT_DATE - interval '4 weeks' " \
                                            "AND updated_at > CURRENT_TIMESTAMP - interval '2 hours'"

        self.undeleted_areas_count_query = "SELECT COUNT(*) FROM upload_area " \
                                           "WHERE created_at > CURRENT_DATE - interval '4 weeks' " \
                                           "AND status != 'DELETED'"

    def health_check(self):
        deadletter_results = self.get_deadletter_count()
        undeleted_upload_area_count = self.parse_and_query_db(self.undeleted_areas_count_query)
        checksumming_areas = self.parse_and_query_db(self.checksumming_areas_count_query)
        validating_areas = self.parse_and_query_db(self.validation_areas_count_query)
        status_info = f"DEADLETTER QUEUE: {deadletter_results['ApproximateNumberOfMessagesVisible']} in queue, " \
                      f"{deadletter_results['NumberOfMessagesReceived']} added in past 24 hrs\n" \
                      f"UPLOAD_AREAS: {undeleted_upload_area_count} undeleted areas, {checksumming_areas} stuck in " \
                      f"checksumming, {validating_areas} stuck in validation"

        attachments = [{
            "title": f"Health Check Report for {self.env}:",
            "color": "good",
            "text": status_info
        }]

        self.post_message_to_url(self.test_webhook, {"attachments": attachments})

    def post_message_to_url(self, url, message):
        body = json.dumps(message)
        headers = {'Content-Type': 'application/json'}
        requests.post(url=url, data=body, headers=headers)

    def get_deadletter_count(self):
        now = datetime.utcnow()
        yesterday = now - timedelta(hours=24)
        metric_data_queries = [
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
                'Id': 'recieved_messages',
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
        response = client.get_metric_data(MetricDataQueries=metric_data_queries, StartTime=yesterday, EndTime=now)
        results = {}
        for info in response['MetricDataResults']:
            results[info['Label']] = info['Values'][0]
        return results

    def parse_and_query_db(self, query):
        query_result = _run_query(query)
        rows = query_result.fetchall()
        if len(rows) > 0:
            results = rows[0][0]
            return results
