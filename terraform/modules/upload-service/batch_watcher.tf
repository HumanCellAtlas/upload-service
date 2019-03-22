resource "aws_iam_role" "batch_watcher_lambda" {
  name = "dcp-upload-batch-watcher-daemon-${var.deployment_stage}"
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

resource "aws_iam_role_policy" "batch_watcher_lambda" {
  name = "dcp-upload-batch-watcher-daemon-${var.deployment_stage}"
  role = "${aws_iam_role.batch_watcher_lambda.name}"
  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
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
        "batch:Describe*"
      ],
      "Resource": [
        "*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:TerminateInstances"
      ],
      "Resource": [
        "*"
      ]
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
      "Sid": "LambdaPolicy",
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": "arn:aws:lambda:${local.aws_region}:${local.account_id}:function:dcp-upload-csum-${var.deployment_stage}"
    }
  ]
}
EOF
}

output "batch_watcher_lambda_role_arn" {
  value = "${aws_iam_role.batch_watcher_lambda.arn}"
}

resource "aws_lambda_function" "batch_watcher_lambda" {
  function_name    = "dcp-upload-batch-watcher-${var.deployment_stage}"
  s3_bucket        = "${aws_s3_bucket.lambda_deployments.id}"
  s3_key           = "batch_watcher_daemon.zip"
  role             = "arn:aws:iam::${local.account_id}:role/dcp-upload-batch-watcher-daemon-${var.deployment_stage}"
  handler          = "app.batch_watcher_handler"
  runtime          = "python3.6"
  memory_size      = 512
  timeout          = 900
  reserved_concurrent_executions = 0

  environment {
    variables = {
      DEPLOYMENT_STAGE = "${var.deployment_stage}",
      API_HOST = "${var.upload_api_fqdn}"
    }
  }
}

resource "aws_cloudwatch_event_rule" "batch_watcher_hourly_rule" {
    name = "batch-watcher-every-hour-${var.deployment_stage}"
    description = "Fires every hour"
    schedule_expression = "cron(0 * * * ? *)"
    count = "${var.deployment_stage == "prod" || var.deployment_stage == "staging" || var.deployment_stage == "integration" || var.deployment_stage == "dev" ? 1 : 0}"
}

resource "aws_cloudwatch_event_target" "hourly_batch_watcher" {
    rule = "${aws_cloudwatch_event_rule.batch_watcher_hourly_rule.name}"
    target_id = "batch_watcher_lambda"
    arn = "${aws_lambda_function.batch_watcher_lambda.arn}"
    count = "${var.deployment_stage == "prod" || var.deployment_stage == "staging" || var.deployment_stage == "integration" || var.deployment_stage == "dev" ? 1 : 0}"
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_batch_watcher" {
    statement_id = "AllowExecutionFromCloudWatch"
    action = "lambda:InvokeFunction"
    function_name = "${aws_lambda_function.batch_watcher_lambda.function_name}"
    principal = "events.amazonaws.com"
    source_arn = "${aws_cloudwatch_event_rule.batch_watcher_hourly_rule.arn}"
    count = "${var.deployment_stage == "prod" || var.deployment_stage == "staging" || var.deployment_stage == "integration" || var.deployment_stage == "dev" ? 1 : 0}"

}
