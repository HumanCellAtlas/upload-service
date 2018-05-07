resource "aws_secretsmanager_secret" "secrets" {
  name = "dcp/upload/${var.deployment_stage}/secrets"
}

resource "aws_secretsmanager_secret_version" "secrets" {
  secret_id = "${aws_secretsmanager_secret.secrets.id}"
  secret_string = <<SECRETS_JSON
{
  "bucket_name": "${aws_s3_bucket.upload_areas_bucket.bucket}",
}
SECRETS_JSON
}
