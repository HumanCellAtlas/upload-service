variable "deployment_stage" {
  type = "string"
  default = "test"
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

variable "vpc_id" {
  type = "string"
}

data "aws_subnet_ids" "vpc" {
  vpc_id = "${var.vpc_id}"
}

data "aws_subnet" "vpc" {
  count = "${length(data.aws_subnet_ids.vpc.ids)}"
  id = "${data.aws_subnet_ids.vpc.ids[count.index]}"
}
