import os

import boto3


class EventNotifier:

    AWS_REGION = 'us-east-1'

    @staticmethod
    def notify(message, channel=None):
        sns = boto3.client('sns')
        topic_arn = "arn:aws:sns:{aws_region}:{account_id}:{topic_name}".format(
            aws_region=EventNotifier.AWS_REGION,
            account_id=boto3.client('sts').get_caller_identity().get('Account'),
            topic_name=os.environ['DCP_EVENTS_TOPIC'])
        publish_args = {
            'Message': f"UPLOAD({os.environ['DEPLOYMENT_STAGE']}): " + message,
            'TopicArn': topic_arn
        }
        if channel:
            publish_args['Subject'] = channel
        sns.publish(**publish_args)
