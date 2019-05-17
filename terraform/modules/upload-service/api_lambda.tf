resource "aws_iam_role" "upload_api_lambda" {
  name = "upload-api-${var.deployment_stage}"
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

resource "aws_iam_role_policy" "upload_api_lambda" {
  name = "upload-api-${var.deployment_stage}"
  role = "${aws_iam_role.upload_api_lambda.name}"

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
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${local.bucket_name}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
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
        "iam:GetUser",
        "iam:CreateUser",
        "iam:DeleteUser",
        "iam:PutUserPolicy",
        "iam:DeleteUserPolicy",
        "iam:ListUserPolicies",
        "iam:CreateAccessKey",
        "iam:DeleteAccessKey",
        "iam:ListAccessKeys",
        "iam:PassRole"
      ],
      "Resource": [
        "arn:aws:iam::${local.account_id}:role/dcp-upload-*",
        "arn:aws:iam::${local.account_id}:user/upload-*",
        "arn:aws:iam::${local.account_id}:policy/dcp-upload-*"
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
        "sqs:SendMessage"
      ],
      "Resource": [
        "arn:aws:sqs:${local.aws_region}:${local.account_id}:dcp-upload-pre-csum-queue-${var.deployment_stage}",
        "arn:aws:sqs:${local.aws_region}:${local.account_id}:dcp-upload-area-deletion-queue-${var.deployment_stage}",
        "arn:aws:sqs:${local.aws_region}:${local.account_id}:dcp-upload-validation-queue-${var.deployment_stage}"
      ]
    }
  ]
}
EOF
}

resource "aws_lambda_function" "upload_api_lambda" {
  function_name    = "upload-api-${var.deployment_stage}"
  role             = "arn:aws:iam::${local.account_id}:role/upload-api-${var.deployment_stage}"
  handler          = "app.app"
  runtime          = "python3.6"
  memory_size      = 512
  timeout          = 300

  environment {
    variables = {
      DEPLOYMENT_STAGE = "${var.deployment_stage}",
      API_HOST = "${var.upload_api_fqdn}"
    }
  }
  tags {
    aws-chalice = "version=1.1.1:stage=${var.deployment_stage}:app=upload-api"
  }
}
