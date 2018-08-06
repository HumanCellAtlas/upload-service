import json
from upload.lambdas.checksum_daemon import ChecksumDaemon


# This lambda function is invoked by messages in the the pre_checksum_upload_queue (AWS SQS).
# The queue and the lambda function are connected via aws_lambda_event_source_mapping
def call_checksum_daemon(event, context):
    unwrapped_event = json.loads(event["Records"][0]["body"])
    ChecksumDaemon(context).consume_event(unwrapped_event)


"""
example event:
{
    'Records': [{
        'messageId': '', 
        'receiptHandle': '',
         'body': '{
            "Records":[{
                "eventVersion":"",
                "eventSource":"",
                "awsRegion":"",
                "eventTime":"",
                "eventName":"",
                "userIdentity":{"principalId":""},
                "requestParameters":{"sourceIPAddress":""},
                "responseElements":{
                    "x-amz-request-id":"",
                    "x-amz-id-2":""
                    },
                "s3":{
                    "s3SchemaVersion":"",
                    "configurationId":"",
                    "bucket":{
                        "name":"",
                        "ownerIdentity":{"principalId":""},
                        "arn":""
                        },
                    "object":{
                        "key":"",
                        "size":Int,
                        "eTag":"",
                        "sequencer":""
                    }
                }
            }]
        }', 
        'attributes': {
            'ApproximateReceiveCount': '', 
            'SentTimestamp': '', 
            'SenderId': '', 
            'ApproximateFirstReceiveTimestamp': ''
        }, 
        'messageAttributes': {}, 
        'md5OfBody': '', 
        'eventSource': '', 
        'eventSourceARN': '', 
        'awsRegion': ''
    }]
}
"""
