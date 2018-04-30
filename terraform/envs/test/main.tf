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
}
