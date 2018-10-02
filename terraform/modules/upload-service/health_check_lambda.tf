resource "aws_iam_role" "upload_health_check_lambda" {
  name = "upload-health-check-${var.deployment_stage}"
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

resource "aws_iam_role_policy" "upload_health_check_lambda" {
  name = "upload-health-check-${var.deployment_stage}"
  role = "${aws_iam_role.upload_health_check_lambda.name}"
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
        "sqs:GetQueueAttributes"
      ],
      "Resource": [
        "arn:aws:sqs:*:*:${aws_sqs_queue.upload_queue.name}"
      ]
    }
  ]
}
EOF
}

resource "aws_s3_bucket" "lambda_deployments" {
  bucket = "${var.bucket_name_prefix}lambda-deployment-${var.deployment_stage}"
  acl = "private"
  force_destroy = "false"
  acceleration_status = "Enabled"
}

resource "aws_lambda_function" "upload_health_check_lambda" {
  function_name    = "dcp-upload-health-check-${var.deployment_stage}"
  s3_bucket        = "${aws_s3_bucket.lambda_deployments.id}"
  s3_key           = "health-check/health_check_daemon.zip"
  role             = "arn:aws:iam::${local.account_id}:role/upload-checksum-daemon-${var.deployment_stage}"
  handler          = "app.health_check"
  runtime          = "python3.6"
  memory_size      = 960
  timeout          = 300

  environment {
    variables = {
      DEPLOYMENT_STAGE = "${var.deployment_stage}",
    }
  }
}
