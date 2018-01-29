import os

import boto3

from ..component import Component


class SnsTopic(Component):

    def __init__(self, name):
        self.name = name
        super().__init__()
        self.sns = boto3.client('sns')
        account_id = boto3.client('sts').get_caller_identity().get('Account')
        self.arn = f"arn:aws:sns:{os.environ['AWS_REGION']}:{account_id}:{self.name}"

    def __str__(self):
        return f"SNS topic {self.name}"

    def is_setup(self):
        topic_arns = [x['TopicArn'] for x in self.sns.list_topics()['Topics']]
        return self.arn in topic_arns

    def set_it_up(self):
        self.sns.create_topic(Name=self.name)

    def tear_it_down(self):
        self.sns.delete_topic(TopicArn=self.arn)

