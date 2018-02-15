variable "deployment_stage" {
  type = "string"
}

variable "bucket_name_prefix" {
  type = "string"
}

variable "vpc_id" {
  type = "string"
}

variable "vpc_default_security_group_id" {
  type = "string"
}

variable "validation_cluster_ec2_key_pair" {
  type = "string"
}

variable "validation_cluster_ami_id" {
  type = "string"
}

variable "csum_cluster_ec2_key_pair" {
  type = "string"
}

data "aws_caller_identity" "current" {}

data "aws_subnet_ids" "vpc" {
  vpc_id = "${var.vpc_id}"
}

data "aws_subnet" "vpc" {
  count = "${length(data.aws_subnet_ids.vpc.ids)}"
  id = "${data.aws_subnet_ids.vpc.ids[count.index]}"
}
