variable "subnet_id" {
  type = "string"
}

variable "subnet_ids" {
  type = "list"
}

variable "vpc_id" {
  type = "string"
}

variable "deployment_stage" {
  type = "string"
}

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
