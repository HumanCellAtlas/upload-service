variable "deployment_stage" {
  type = "string"
  default = "test"
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
