import json
import os

import requests

from upload.common.logging import get_logger

logger = get_logger(__name__)


def health_check(event, context):
    logger.debug("Running a health check for {}. Results will be posted in #upload-service".format(
        os.environ['DEPLOYMENT_STAGE'])
    )
    webhook = "https://hooks.slack.com/services/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"
    test_webhook = "https://hooks.slack.com/services/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"
    post_message_to_url(test_webhook, 'test test test')


def post_message_to_url(url, message):
    body = json.dumps(message)
    headers = {'Content-Type': 'application/json'}
    requests.post(url, data=body, headers=headers)