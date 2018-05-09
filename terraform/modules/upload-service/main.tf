module "upload-service-database" {
  source = "../../modules/database"
  deployment_stage = "${var.deployment_stage}"
  vpc_rds_security_group_id = "${var.vpc_rds_security_group_id}"
  db_username = "${var.db_username}"
  db_password = "${var.db_password}"
  db_instance_count = "${var.db_instance_count}"
}
