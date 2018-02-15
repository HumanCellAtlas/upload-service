terraform {
  required_version = "=0.11.3"

  backend "s3" {
    // bucket = "" - Provided on command line with:
    //     tf init -backend-config="bucket=my-tf-bucket"
    key = "terraform/upload-service/envs/dev/state.tfstate"
    region = "us-east-1"
    profile = "default"
  }
}

provider "aws" {
  version = ">= 1.8"
  region = "us-east-1"
  profile = "default"
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
}

output "validation_job_q_arn" {
  value = "${module.upload-service.validation_job_q_arn}"
}

output "validation_job_role_arn" {
  value = "${module.upload-service.validation_job_role_arn}"
}
