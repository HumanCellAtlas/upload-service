resource "aws_secretsmanager_secret" "secrets" {
  name = "dcp/upload/${var.deployment_stage}/secrets"
}

resource "aws_secretsmanager_secret_version" "secrets" {
  secret_id = "${aws_secretsmanager_secret.secrets.id}"
  //
  // HEY YOU!  DEVELOPER!
  //
  // Keep this list in sync with BOGO_CONFIG in tests/unit/__init__.py
  //
  secret_string = <<SECRETS_JSON
{
  "api_key": "${var.ingest_api_key}",
  "area_deletion_q_url": "${aws_sqs_queue.area_deletion_queue.id}",
  "area_deletion_lambda_name": "${aws_lambda_function.area_deletion_lambda.function_name}",
  "bucket_name": "${aws_s3_bucket.upload_areas_bucket.bucket}",
  "csum_job_q_arn": "${aws_batch_job_queue.csum_job_q.arn}",
  "csum_job_role_arn": "${aws_iam_role.csum_job_role.arn}",
  "csum_upload_q_url": "${aws_sqs_queue.upload_queue.id}",
  "ingest_api_host": "${var.ingest_api_host}",
  "slack_webhook": "${var.slack_webhook}",
  "staging_bucket_arn": "${var.staging_bucket_arn}",
  "upload_submitter_role_arn": "${aws_iam_role.upload_submitter.arn}",
  "validation_job_q_arn": "${aws_batch_job_queue.validation_job_q.arn}",
  "validation_job_role_arn": "${aws_iam_role.validation_job_role.arn}",
  "validation_q_url": "${aws_sqs_queue.validation_queue.id}"
}
SECRETS_JSON
}

resource "aws_secretsmanager_secret" "outgoing_ingest_auth" {
  name = "dcp/upload/${var.deployment_stage}/outgoing_ingest_auth"
}

resource "aws_secretsmanager_secret_version" "outgoing_ingest_auth" {
  secret_id = "${aws_secretsmanager_secret.outgoing_ingest_auth.id}"
  secret_string = <<SECRETS_JSON
{
  "dcp_auth0_audience": "${var.dcp_auth0_audience}",
  "gcp_service_acct_creds": "${var.gcp_service_acct_creds}"
}
SECRETS_JSON
}

resource "aws_secretsmanager_secret" "incoming_service_auth" {
  name = "dcp/upload/${var.deployment_stage}/incoming_auth"
}

resource "aws_secretsmanager_secret_version" "incoming_service_auth" {
  secret_id = "${aws_secretsmanager_secret.incoming_service_auth.id}"
  secret_string = <<SECRETS_JSON
{
  "openid_provider": "${var.openid_provider}",
  "oidc_audience": "${var.oidc_audience}",
  "oidc_group_claim": "${var.oidc_group_claim}",
  "oidc_email_claim": "${var.oidc_email_claim}",
  "authorized_gcp_project_domain": "${var.authorized_gcp_project_domain}"
}
SECRETS_JSON
}
