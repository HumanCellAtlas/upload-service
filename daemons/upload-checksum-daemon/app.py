import json
from upload.lambdas.checksum_daemon import ChecksumDaemon


def call_checksum_daemon(event, context):
    message = json.loads(event["Records"][0]["body"])
    ChecksumDaemon(context).consume_event(message)
