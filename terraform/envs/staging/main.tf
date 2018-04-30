terraform {
  required_version = "=0.11.7"

  backend "s3" {
    bucket  = "org-humancellatlas-dcp-infra"
    key     = "terraform/upload-service/envs/staging/state.tfstate"
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

module "upload-service" {
  source = "../../modules/upload-service"
  deployment_stage = "${var.deployment_stage}"
  bucket_name_prefix = "${var.bucket_name_prefix}"

  vpc_id = "${var.vpc_id}"
  vpc_default_security_group_id = "${var.vpc_default_security_group_id}"

  // Validation Batch infrastructure.
  validation_cluster_ec2_key_pair = "${var.validation_cluster_ec2_key_pair}"
  validation_cluster_ami_id = "${var.validation_cluster_ami_id}"

  // Checksumming Batch infrastructure.
  csum_cluster_ec2_key_pair = "${var.csum_cluster_ec2_key_pair}"
}

module "upload-service-database" {
  source = "../../modules/database"
  deployment_stage = "${var.deployment_stage}"
  vpc_rds_security_group_id = "${var.vpc_rds_security_group_id}"
}

output "validation_job_q_arn" {
  value = "${module.upload-service.validation_job_q_arn}"
}

output "validation_job_role_arn" {
  value = "${module.upload-service.validation_job_role_arn}"
}

output "csum_job_q_arn" {
  value = "${module.upload-service.csum_job_q_arn}"
}

output "csum_job_role_arn" {
  value = "${module.upload-service.csum_job_role_arn}"
}
