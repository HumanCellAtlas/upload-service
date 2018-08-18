resource "aws_db_subnet_group" "db_subnet_group" {
  name       = "upload_db_subnet_group"
  subnet_ids = ["${var.lb_subnet_ids}"]

  tags {
    Name = "DCP Upload DB Subnet Group"
  }
}
