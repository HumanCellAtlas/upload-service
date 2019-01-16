variable "deployment_stage" {
  type = "string"
}

variable "slack_webhook" {
  type="string"
}

// VPC

variable "vpc_cidr_block" {
  type = "string"
}

// S3

variable "bucket_name_prefix" {
  type = "string"
}

variable "staging_bucket_arn" {
  type = "string"
}

// API Lambda

variable "upload_api_fqdn" {
  type = "string"
}
variable "ingest_api_key" {
  type = "string"
}

// Checksum Lambda
variable "csum_docker_image" {
  type = "string"
  default = "humancellatlas/upload-checksummer:2"
}

// Batch

variable "validation_cluster_ec2_key_pair" {
  type = "string"
}
variable "validation_cluster_ami_id" {
  type = "string"
}
variable "validation_cluster_min_vcpus" {
  type = "string"
}

variable "csum_cluster_ec2_key_pair" {
  type = "string"
}
variable "csum_cluster_min_vcpus" {
  type = "string"
}

# Database

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

variable "ingest_api_host" {
  type = "string"
}

# Auth

variable "dcp_auth0_audience" {
  type = "string"
}

variable "gcp_service_acct_creds" {
  type = "string"
}

# Data Sources

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_subnet_ids" "upload_vpc" {
  vpc_id = "${module.upload-vpc.vpc_id}"
}
