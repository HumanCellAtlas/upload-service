resource "aws_iam_role" "checksum_lambda" {
  name = "checksum-${var.deployment_stage}"
  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "",
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy" "checksum_lambda" {
  name = "checksum-${var.deployment_stage}"
  role = "${aws_iam_role.checksum_lambda.name}"

    policy = <<EOF
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
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ChangeMessageVisibility",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:ReceiveMessage"
      ],
      "Resource": [
        "arn:aws:sqs:*:*:${aws_sqs_queue.upload_queue.name}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:DescribeSecret",
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:${local.account_id}:secret:dcp/upload/${var.deployment_stage}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
          "s3:GetObject",
          "s3:GetObjectTagging",
          "s3:PutObjectTagging"
      ],
      "Resource": [
          "arn:aws:s3:::${aws_s3_bucket.upload_areas_bucket.bucket}/*"
      ]
    }
  ]
}
EOF
}

resource "aws_lambda_function" "checksum_lambda" {
  function_name    = "checksum-${var.deployment_stage}"
  s3_bucket        = "test-checksum-lambda"
  s3_key           = "v1.0.0/checksum_daemon.zip"
  role             = "arn:aws:iam::${local.account_id}:role/checksum-${var.deployment_stage}"
  handler          = "app.call_checksum_daemon"
  runtime          = "python3.6"
  memory_size      = 512
  timeout          = 300

  environment {
    variables = {
      DEPLOYMENT_STAGE = "${var.deployment_stage}",
      INGEST_API_KEY = "${var.ingest_api_key}",
      INGEST_AMQP_SERVER = "${var.ingest_amqp_server}",
      API_HOST = "${var.upload_api_fqdn}",
      CSUM_DOCKER_IMAGE = "humancellatlas/upload-checksummer:2"
    }
  }
}
