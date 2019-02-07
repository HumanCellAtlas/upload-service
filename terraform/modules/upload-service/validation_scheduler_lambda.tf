resource "aws_iam_role" "validation_scheduler_lambda" {
  name = "validation-scheduler-daemon-${var.deployment_stage}"
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

resource "aws_iam_role_policy" "validation_scheduler_lambda" {
  name = "validation-scheduler-daemon-${var.deployment_stage}"
  role = "${aws_iam_role.validation_scheduler_lambda.name}"
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
        "logs:DescribeLogStreams"
      ],
      "Resource": [
        "arn:aws:logs:*:*:*"
      ],
      "Effect": "Allow"
    },
    {
      "Sid": "LambdaObjectLogging",
      "Action": [
        "logs:PutLogEvents"
      ],
      "Resource": [
        "arn:aws:logs:*:*:/aws/lambda/${aws_lambda_function.validation_scheduler_lambda.function_name}:*"
      ],
      "Effect": "Allow"
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectTagging"
      ],
      "Resource": [
        "arn:aws:s3:::${local.bucket_name}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${local.bucket_name}"
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
        "sqs:ReceiveMessage",
        "sqs:SendMessage"
      ],
      "Resource": [
        "arn:aws:sqs:*:*:${aws_sqs_queue.validation_queue.name}"
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
        "*"
      ]
    }
  ]
}
EOF
}

output "validation_scheduler_lambda_role_arn" {
  value = "${aws_iam_role.validation_scheduler_lambda.arn}"
}


resource "aws_lambda_function" "validation_scheduler_lambda" {
  function_name    = "dcp-upload-validation-scheduler-${var.deployment_stage}"
  s3_bucket        = "${aws_s3_bucket.lambda_deployments.id}"
  s3_key           = "validation_scheduler_daemon.zip"
  role             = "arn:aws:iam::${local.account_id}:role/validation-scheduler-daemon-${var.deployment_stage}"
  handler          = "app.schedule_file_validation"
  runtime          = "python3.6"
  memory_size      = 500
  timeout          = 900

  environment {
    variables = {
      DEPLOYMENT_STAGE = "${var.deployment_stage}",
      INGEST_API_KEY = "${var.ingest_api_key}",
      API_HOST = "${var.upload_api_fqdn}"
    }
  }
}
