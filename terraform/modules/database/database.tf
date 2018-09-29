resource "aws_rds_cluster_instance" "cluster_instances" {
  count              = "${var.db_instance_count}"
  identifier         = "upload-cluster-${var.deployment_stage}-${count.index}"
  cluster_identifier = "${aws_rds_cluster.upload.id}"
  instance_class     = "db.r4.large"
  publicly_accessible = "true"
  engine                  = "aurora-postgresql"
  engine_version          = "9.6.8"
  auto_minor_version_upgrade = "true"
  performance_insights_enabled = "true"
  preferred_maintenance_window = "sat:09:08-sat:09:38"
}

resource "aws_rds_cluster" "upload" {
  apply_immediately       = "false"
  cluster_identifier      = "upload-${var.deployment_stage}"
  engine                  = "aurora-postgresql"
  engine_version          = "9.6.8"
  availability_zones      = ["us-east-1a", "us-east-1c", "us-east-1d"]
  database_name           = "upload_${var.deployment_stage}"
  master_username         = "${var.db_username}"
  master_password         = "${var.db_password}"
  backup_retention_period = 7
  port                    = 5432
  preferred_backup_window = "07:27-07:57"
  preferred_maintenance_window = "sat:09:08-sat:09:38"
  storage_encrypted       = "true"
  skip_final_snapshot     = "true"
  vpc_security_group_ids  = ["${aws_security_group.rds-postgres.id}"]
  db_subnet_group_name    = "${aws_db_subnet_group.db_subnet_group.name}"
  db_cluster_parameter_group_name = "default.aurora-postgresql9.6"
}
