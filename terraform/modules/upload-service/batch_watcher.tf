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

  environment {
    variables = {
      DEPLOYMENT_STAGE = "${var.deployment_stage}",
      INGEST_API_KEY = "${var.ingest_api_key}",
      API_HOST = "${var.upload_api_fqdn}"
    }
  }
}
