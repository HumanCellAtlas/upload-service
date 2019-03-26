variable "deployment_stage" {
  type = "string"
  default = "test"
}

variable "vpc_cidr_block" {
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
variable "preferred_maintenance_window" {
  type = "string"
}
