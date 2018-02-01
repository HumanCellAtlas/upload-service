"""
Some of the infrastructure for the #dcp-events slack channel
"""

import json
import os

from preform import CompositeComponent
from preform.aws import IAMRole, RoleInlinePolicy, SnsTopic


class DcpEventsSnsTopic(SnsTopic):

    def __init__(self, **options):
        super().__init__(name=os.environ['DCP_EVENTS_TOPIC'], **options)


class DcpEventsRole(IAMRole):
    def __init__(self, **options):
        super().__init__(name='dcp-events-slackbot', trust_document=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "lambda.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }),
            **options
        )


class DcpEventsRoleInlinePolicy(RoleInlinePolicy):
    def __init__(self, **options):
        super().__init__(role_name="dcp-events-slackbot",
                         name="dcp-events-slackbot",
                         policy_document=json.dumps(
                             {
                                 "Version": "2012-10-17",
                                 "Statement": [
                                     {
                                         "Effect": "Allow",
                                         "Action": [
                                             "logs:CreateLogGroup",
                                             "logs:CreateLogStream",
                                             "logs:PutLogEvents"
                                         ],
                                         "Resource": [
                                             "arn:aws:logs:*:*:*"
                                         ]
                                     }
                                 ]
                             }),
                         **options)


class SlackFeed(CompositeComponent):

    SUBCOMPONENTS = {
        'sns-topic': DcpEventsSnsTopic,
        'events-role': DcpEventsRole,
        'events-role-policy': DcpEventsRoleInlinePolicy,
    }

    def __str__(self):
        return "Slack Feed:"
