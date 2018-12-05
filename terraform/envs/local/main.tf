terraform {
  required_version = "=0.11.10"

  backend "s3" {
    bucket  = "org-humancellatlas-upload-infra"
    key     = "terraform/envs/local/state.tfstate"
    encrypt = true
    region  = "us-east-1"
    profile = "hca"
  }
}

provider "aws" {
  version = ">= 1.31"
  region = "us-east-1"
  profile = "hca"
}

// This is a dummy secrets to make config/environment happy

resource "aws_secretsmanager_secret" "secrets" {
  name = "dcp/upload/${var.deployment_stage}/secrets"
}

resource "aws_secretsmanager_secret_version" "secrets" {
  secret_id = "${aws_secretsmanager_secret.secrets.id}"
  secret_string = <<SECRETS_JSON
{
  "api_key": "dummy-value-to-keep-environment-script-happy"
}
SECRETS_JSON
}

// Database secret using local Postgres

resource "aws_secretsmanager_secret" "database-secrets" {
  name = "dcp/upload/${var.deployment_stage}/database"
}

resource "aws_secretsmanager_secret_version" "database-secrets" {
  secret_id = "${aws_secretsmanager_secret.database-secrets.id}"
  secret_string = <<SECRETS_JSON
{
  "database_uri": "postgresql://:@localhost/upload_${var.deployment_stage}",
  "pgbouncer_uri": "postgresql://:@localhost/upload_${var.deployment_stage}"
}
SECRETS_JSON
}
