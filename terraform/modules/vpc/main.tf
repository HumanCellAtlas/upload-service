variable "component_name" {
  type = string
}

variable "deployment_stage" {
  type = string
}

variable "vpc_cidr_block" {
  type = string
}

variable "subnet_bits" {
  type = string
  default = "4"
}

output "vpc_id" {
  value =  aws_vpc.vpc.id
}

output "vpc_default_security_group_id" {
  value =  aws_vpc.vpc.default_security_group_id
}

