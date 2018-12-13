resource "aws_secretsmanager_secret" "secrets" {
  name = "dcp/upload/${var.deployment_stage}/secrets"
}

resource "aws_secretsmanager_secret_version" "secrets" {
  secret_id = "${aws_secretsmanager_secret.secrets.id}"
  secret_string = <<SECRETS_JSON
{
  "bucket_name": "${aws_s3_bucket.upload_areas_bucket.bucket}",
  "validation_job_q_arn": "${aws_batch_job_queue.validation_job_q.arn}",
  "validation_job_role_arn": "${aws_iam_role.validation_job_role.arn}",
  "csum_job_q_arn": "${aws_batch_job_queue.csum_job_q.arn}",
  "csum_upload_q_url": "${aws_sqs_queue.upload_queue.id}",
  "csum_job_role_arn": "${aws_iam_role.csum_job_role.arn}",
  "upload_submitter_role_arn": "${aws_iam_role.upload_submitter.arn}",
  "api_key": "${var.ingest_api_key}",
  "slack_webhook": "${var.slack_webhook}"
}
SECRETS_JSON
}
