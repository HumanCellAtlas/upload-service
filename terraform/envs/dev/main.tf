terraform {
  required_version = "=0.11.13"

  backend "s3" {
    bucket  = "org-humancellatlas-upload-infra"
    key     = "terraform/envs/dev/state.tfstate"
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

module "upload-service" {
  source = "../../modules/upload-service"
  deployment_stage = "${var.deployment_stage}"

  // VPC
  vpc_cidr_block = "${var.vpc_cidr_block}"

  // S3
  bucket_name_prefix = "${var.bucket_name_prefix}"
  staging_bucket_arn = "${var.staging_bucket_arn}"

  // DNS
  parent_zone_domain_name = "${var.parent_zone_domain_name}"

  // API Lambda
  upload_api_fqdn = "${var.upload_api_fqdn}"
  ingest_api_key = "${var.ingest_api_key}"

  // API Gateway
  upload_api_api_gateway_id = "${var.upload_api_api_gateway_id}"

  // Checksum Lambda
  csum_docker_image = "${var.csum_docker_image}"

  // Validation Batch infrastructure.
  validation_cluster_ec2_key_pair = "${var.validation_cluster_ec2_key_pair}"
  validation_cluster_ami_id = "${var.validation_cluster_ami_id}"
  validation_cluster_instance_type = "${var.validation_cluster_instance_type}"
  validation_cluster_min_vcpus = "${var.validation_cluster_min_vcpus}"

  // Checksumming Batch infrastructure.
  csum_cluster_ec2_key_pair = "${var.csum_cluster_ec2_key_pair}"
  csum_cluster_instance_type = "${var.csum_cluster_instance_type}"
  csum_cluster_min_vcpus = "${var.csum_cluster_min_vcpus}"

  // Database
  db_username = "${var.db_username}"
  db_password = "${var.db_password}"
  db_instance_count = "${var.db_instance_count}"
  preferred_maintenance_window = "${var.preferred_maintenance_window}"

  // DCP Ingest
  ingest_api_host = "${var.ingest_api_host}"

  // AUTH
  dcp_auth0_audience = "${var.dcp_auth0_audience}"
  gcp_service_acct_creds = "${var.gcp_service_acct_creds}"

  // Slack
  slack_webhook = "${var.slack_webhook}"
}

output "upload_csum_lambda_role_arn" {
  value = "${module.upload-service.upload_csum_lambda_role_arn}"
}
