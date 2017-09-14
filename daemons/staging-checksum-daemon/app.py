import os, json

# import boto3
import domovoi

import sys

pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), 'domovoilib'))  # noqa
sys.path.insert(0, pkg_root)  # noqa

from staging.checksum_daemon import ChecksumDaemon

app = domovoi.Domovoi()


# Set use_sns=False to subscribe your Lambda directly to S3 events without forwrading them through an SNS topic.
# This has fewer moving parts, but you can only subscribe one Lambda function to events in a given S3 bucket.
@app.s3_event_handler(bucket=os.environ['STAGING_S3_BUCKET'], events=["s3:ObjectCreated:*"], use_sns=False)
def monitor_s3(event, context):
    ChecksumDaemon(context).consume_event(event)
