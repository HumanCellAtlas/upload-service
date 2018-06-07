variable "vpc_id" {
  type = "string"
}

variable "vpc_default_security_group_id" {
  type = "string"
}

variable "deployment_stage" {
  type = "string"
}

// S3

variable "bucket_name_prefix" {
  type = "string"
}

// API Lambda

variable "upload_api_fqdn" {
  type = "string"
}
variable "ingest_api_key" {
  type = "string"
}

// Batch

variable "validation_cluster_ec2_key_pair" {
  type = "string"
}

variable "validation_cluster_ami_id" {
  type = "string"
}

variable "csum_cluster_ec2_key_pair" {
  type = "string"
}

# Database

variable "vpc_rds_security_group_id" {
  type = "string"
}

variable "db_username" {
  type = "string"
}

variable "db_password" {
  type = "string"
}

variable "db_instance_count" {
  type = "string"
  default = 2
}

# DCP Ingest

variable "ingest_amqp_server" {
  type = "string"
}

# Data Sources

data "aws_caller_identity" "current" {}

data "aws_subnet_ids" "vpc" {
  vpc_id = "${var.vpc_id}"
}

data "aws_subnet" "vpc" {
  count = "${length(data.aws_subnet_ids.vpc.ids)}"
  id = "${data.aws_subnet_ids.vpc.ids[count.index]}"
}
