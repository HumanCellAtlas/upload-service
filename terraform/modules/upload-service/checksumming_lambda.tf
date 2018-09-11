resource "aws_iam_role" "upload_csum_lambda" {
  name = "upload-checksum-daemon-${var.deployment_stage}"
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

resource "aws_iam_role_policy" "upload_csum_lambda" {
  name = "upload-checksum-daemon-${var.deployment_stage}"
  role = "${aws_iam_role.upload_csum_lambda.name}"
  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LambdaPolicy",
      "Action": [
        "events:*",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:ListRoles",
        "iam:PassRole"
      ],
      "Resource": "*",
      "Effect": "Allow"
    },
    {
      "Sid": "LambdaLogging",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams"
      ],
      "Resource": [
        "arn:aws:logs:*:*:*"
      ],
      "Effect": "Allow"
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectTagging",
        "s3:PutObjectTagging"
      ],
      "Resource": [
        "arn:aws:s3:::${local.bucket_name}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "batch:Describe*",
        "batch:RegisterJobDefinition",
        "batch:SubmitJob"
      ],
      "Resource": [
        "arn:aws:batch:*:${local.account_id}:*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:DescribeSecret",
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:${local.aws_region}:${local.account_id}:secret:dcp/upload/${var.deployment_stage}/*"
      ]
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
    }
  ]
}
EOF
}

output "upload_csum_lambda_role_arn" {
  value = "${aws_iam_role.upload_csum_lambda.arn}"
}


resource "aws_s3_bucket" "lambda_area_bucket" {
  bucket = "${var.bucket_name_prefix}checksum-lambda-deployment"
  acl = "private"
  force_destroy = "false"
  acceleration_status = "Enabled"
}

resource "aws_lambda_function" "upload_checksum_lambda" {
  function_name    = "dcp-upload-csum-${var.deployment_stage}"
  s3_bucket        = "${aws_s3_bucket.lambda_area_bucket.id}"
  s3_key           = "${var.deployment_stage}/checksum_daemon.zip"
  role             = "arn:aws:iam::${local.account_id}:role/upload-checksum-daemon-${var.deployment_stage}"
  handler          = "app.call_checksum_daemon"
  runtime          = "python3.6"
  memory_size      = 768
  timeout          = 300

  environment {
    variables = {
      DEPLOYMENT_STAGE = "${var.deployment_stage}",
      INGEST_API_KEY = "${var.ingest_api_key}",
      INGEST_AMQP_SERVER = "${var.ingest_amqp_server}",
      API_HOST = "${var.upload_api_fqdn}",
      CSUM_DOCKER_IMAGE = "${var.csum_docker_image}"
    }
  }
}
