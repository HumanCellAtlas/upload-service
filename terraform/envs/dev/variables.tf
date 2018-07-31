variable "deployment_stage" {
  type = "string"
}
variable "vpc_id" {
  type = "string"
}
variable "vpc_default_security_group_id" {
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
variable "validation_cluster_min_vcpus" {
  type = "string"
}
variable "csum_cluster_ec2_key_pair" {
  type = "string"
}
variable "csum_cluster_min_vcpus" {
  type = "string"
}

// RDS

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
}

// DCP Ingest

variable "ingest_amqp_server" {
  type = "string"
}
