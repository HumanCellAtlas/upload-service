resource "aws_db_subnet_group" "db_subnet_group" {
  name       = "upload_db_subnet_group_${var.deployment_stage}"
  subnet_ids = ["${var.lb_subnet_ids}"]

  tags {
    Name = "DCP Upload ${var.deployment_stage} DB Subnet Group"
  }
}
