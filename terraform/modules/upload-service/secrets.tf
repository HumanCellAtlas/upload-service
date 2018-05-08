resource "aws_secretsmanager_secret" "secrets" {
  name = "dcp/upload/${var.deployment_stage}/secrets"
}

resource "aws_secretsmanager_secret_version" "secrets" {
  secret_id = "${aws_secretsmanager_secret.secrets.id}"
  secret_string = <<SECRETS_JSON
{
  "bucket_name": "${aws_s3_bucket.upload_areas_bucket.bucket}",
  "database_uri": "${module.upload-service-database.database_uri}",
  "validation_job_q_arn": "${aws_batch_job_queue.validation_job_q.arn}",
  "validation_job_role_arn": "${aws_iam_role.validation_job_role.arn}",
  "csum_job_q_arn": "${aws_batch_job_queue.csum_job_q.arn}",
  "csum_job_role_arn": "${aws_iam_role.csum_job_role.arn}",
}
SECRETS_JSON
}
