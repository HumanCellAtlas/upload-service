resource "aws_sqs_queue" "upload_queue" {
  name                      = "dcp-upload-pre-csum-queue-${var.deployment_stage}"
//  Queue visibility timeout must be larger than (triggered lambda) function timeout
  visibility_timeout_seconds = 360
  message_retention_seconds = 86400
  redrive_policy            = "{\"deadLetterTargetArn\":\"${aws_sqs_queue.deadletter_queue.arn}\",\"maxReceiveCount\":4}"

}


resource "aws_sqs_queue" "deadletter_queue" {
  name                      = "dcp-upload-pre-csum-deadletter-queue-${var.deployment_stage}"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue_policy" "pre_checksum_upload_queue_access" {
  queue_url = "${aws_sqs_queue.upload_queue.id}"

  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Id": "sqspolicy",
  "Statement": [
    {
      "Sid": "First",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "sqs:SendMessage",
      "Resource": "arn:aws:sqs:*:*:dcp-upload-pre-csum-queue-${var.deployment_stage}",
      "Condition": {
        "ArnEquals": {
          "aws:SourceArn": "${aws_s3_bucket.upload_areas_bucket.arn}"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateEventSourceMapping",
        "lambda:ListEventSourceMappings",
        "lambda:ListFunction"
      ],
      "Resource": [
        "arn:aws:lambda:*:*:function:checksum-${var.deployment_stage}"
      ]
    }
  ]
}
POLICY
}


resource "aws_lambda_event_source_mapping" "event_source_mapping" {
  batch_size = 1
  event_source_arn  = "${aws_sqs_queue.upload_queue.arn}"
  enabled           = true
  function_name     = "${aws_lambda_function.upload_checksum_lambda.arn}"
}