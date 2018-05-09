terraform {
  required_version = "=0.11.7"

  backend "s3" {
    bucket  = "org-humancellatlas-dcp-infra"
    key     = "terraform/upload-service/envs/test/state.tfstate"
    encrypt = true
    region  = "us-east-1"
    profile = "hca-id"
  }
}

provider "aws" {
  version = ">= 1.16"
  region = "us-east-1"
  profile = "hca"
}

module "upload-service-database" {
  source = "../../modules/database"
  deployment_stage = "${var.deployment_stage}"
  vpc_rds_security_group_id = "${var.vpc_rds_security_group_id}"
  db_username = "${var.db_username}"
  db_password = "${var.db_password}"
  db_instance_count = "${var.db_instance_count}"
}

resource "aws_secretsmanager_secret" "secrets" {
  name = "dcp/upload/${var.deployment_stage}/secrets"
}

resource "aws_secretsmanager_secret_version" "secrets" {
  secret_id = "${aws_secretsmanager_secret.secrets.id}"
  secret_string = <<SECRETS_JSON
{
  "database_uri": "${module.upload-service-database.database_uri}"
}
SECRETS_JSON
}
