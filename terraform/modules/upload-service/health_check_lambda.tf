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
      "Sid": "CloudWatchAccess",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricData"
      ],
      "Resource": [
        "*"
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
  role             = "arn:aws:iam::${local.account_id}:role/upload-health-check-${var.deployment_stage}"
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

resource "aws_cloudwatch_event_rule" "daily" {
    name = "every-day"
    description = "Fires every day at 14:00 UTC"
    schedule_expression = "cron(0 14 * * ? *)"
}

resource "aws_cloudwatch_event_target" "daily_health_check" {
    rule = "${aws_cloudwatch_event_rule.daily.name}"
    target_id = "upload_health_check_lambda"
    arn = "${aws_lambda_function.upload_health_check_lambda.arn}"
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_health_check" {
    statement_id = "AllowExecutionFromCloudWatch"
    action = "lambda:InvokeFunction"
    function_name = "${aws_lambda_function.upload_health_check_lambda.function_name}"
    principal = "events.amazonaws.com"
    source_arn = "${aws_cloudwatch_event_rule.daily.arn}"
}