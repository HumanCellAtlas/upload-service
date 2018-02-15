variable "deployment_stage" {
  type = "string"
  default = "staging"
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
