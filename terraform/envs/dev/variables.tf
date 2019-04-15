variable "deployment_stage" {
  type = "string"
}

variable "slack_webhook" {
  type = "string"
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


// DNS

variable "parent_zone_domain_name" {
  type = "string"
}

variable "upload_api_fqdn" {
  type = "string"
}

// API Lambda

variable "ingest_api_key" {
  type = "string"
}

// Checksum Lambda

variable "csum_docker_image" {
  type = "string"
}

// Batch

variable "validation_cluster_ec2_key_pair" {
  type = "string"
}
variable "validation_cluster_ami_id" {
  type = "string"
}
variable "validation_cluster_instance_type" {
  type = "string"
}
variable "validation_cluster_min_vcpus" {
  type = "string"
}
variable "csum_cluster_ec2_key_pair" {
  type = "string"
}
variable "csum_cluster_instance_type" {
  type = "string"
}
variable "csum_cluster_min_vcpus" {
  type = "string"
}

// RDS

variable "db_username" {
  type = "string"
}
variable "db_password" {
  type = "string"
}
variable "db_instance_count" {
  type = "string"
}
variable "preferred_maintenance_window" {
  type = "string"
}

// DCP Ingest

variable "ingest_api_host" {
  type = "string"
}

// AUTH

variable "dcp_auth0_audience" {
  type = "string"
}

variable "gcp_service_acct_creds" {
  type = "string"
}

variable "openid_provider" {
  type = "string"
}

variable "oidc_audience" {
  type = "string"
}

variable "oidc_group_claim" {
  type = "string"
}

variable "oidc_email_claim" {
  type = "string"
}

variable "authorized_gcp_project_domain" {
  type = "string"
}
