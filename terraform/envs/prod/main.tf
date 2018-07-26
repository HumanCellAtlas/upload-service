terraform {
  required_version = "=0.11.7"

  backend "s3" {
    bucket  = "org-humancellatlas-upload-prod-infra"
    key     = "terraform/envs/prod/state.tfstate"
    encrypt = true
    region  = "us-east-1"
    profile = "hca-prod"
  }
}

provider "aws" {
  version = ">= 1.16"
  region = "us-east-1"
  profile = "hca-prod"
}

module "upload-service" {
  source = "../../modules/upload-service"
  deployment_stage = "${var.deployment_stage}"

  vpc_id = "${var.vpc_id}"
  vpc_default_security_group_id = "${var.vpc_default_security_group_id}"

  // S3
  bucket_name_prefix = "${var.bucket_name_prefix}"

  // API Lambda
  upload_api_fqdn = "${var.upload_api_fqdn}"
  ingest_api_key = "${var.ingest_api_key}"

  // Validation Batch infrastructure.
  validation_cluster_ec2_key_pair = "${var.validation_cluster_ec2_key_pair}"
  validation_cluster_ami_id = "${var.validation_cluster_ami_id}"
  validation_cluster_min_vcpus = "${var.validation_cluster_min_vcpus}"

  // Checksumming Batch infrastructure.
  csum_cluster_ec2_key_pair = "${var.csum_cluster_ec2_key_pair}"
  csum_cluster_min_vcpus = "${var.csum_cluster_min_vcpus}"

  // Database
  vpc_rds_security_group_id = "${var.vpc_rds_security_group_id}"
  db_username = "${var.db_username}"
  db_password = "${var.db_password}"
  db_instance_count = "${var.db_instance_count}"

  // DCP Ingest
  ingest_amqp_server = "${var.ingest_amqp_server}"
}
