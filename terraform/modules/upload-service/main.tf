locals {
  bucket_name = "${var.bucket_name_prefix}${var.deployment_stage}"
  account_id = "${data.aws_caller_identity.current.account_id}"
}

module "upload-service-database" {
  source = "../../modules/database"
  deployment_stage = "${var.deployment_stage}"
  vpc_rds_security_group_id = "${var.vpc_rds_security_group_id}"
  db_username = "${var.db_username}"
  db_password = "${var.db_password}"
  db_instance_count = "${var.db_instance_count}"
  pgbouncer_subnet_id = "${element(data.aws_subnet_ids.vpc.ids, 0)}"
  lb_subnet_ids = "${data.aws_subnet_ids.vpc.ids}"
  vpc_id = "${var.vpc_id}"
}
