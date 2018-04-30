data "aws_secretsmanager_secret" "db_creds" {
  name = "dcp/upload/${var.deployment_stage}/database"
}

data "aws_secretsmanager_secret_version" "db_creds" {
  secret_id = "${data.aws_secretsmanager_secret.db_creds.id}"
}

data "external" "secrets_processing" {  
  program = ["python", "${path.root}/../../../scripts/process_db_secrets.py"]
 
  query = {  
    # arbitrary map from strings to strings, passed  
    # to the external program as the data query. 
    secret_string = "${data.aws_secretsmanager_secret_version.db_creds.secret_string}"
 }
}

resource "aws_rds_cluster_instance" "cluster_instances" {
  count              = 2
  identifier         = "upload-cluster-${var.deployment_stage}-${count.index}"
  cluster_identifier = "${aws_rds_cluster.upload.id}"
  instance_class     = "db.r4.large"
  publicly_accessible = "true"
  engine                  = "aurora-postgresql"
  engine_version          = "9.6.3"
  auto_minor_version_upgrade = "true"
  performance_insights_enabled = "true"
  preferred_maintenance_window = "sat:09:08-sat:09:38"
}

resource "aws_rds_cluster" "upload" {
  apply_immediately       = "false"
  cluster_identifier      = "upload-${var.deployment_stage}"
  engine                  = "aurora-postgresql"
  engine_version          = "9.6.3"
  availability_zones      = ["us-east-1a", "us-east-1c", "us-east-1d"]
  database_name           = "upload_${var.deployment_stage}"
  master_username         = "${data.external.secrets_processing.result.username}"
  master_password         = "${data.external.secrets_processing.result.password}"
  backup_retention_period = 7
  port                    = 5432
  preferred_backup_window = "07:27-07:57"
  preferred_maintenance_window = "sat:09:08-sat:09:38"
  storage_encrypted       = "true"
  skip_final_snapshot     = "true"
  vpc_security_group_ids  = ["${var.vpc_rds_security_group_id}"]
  db_subnet_group_name    = "default"
  db_cluster_parameter_group_name = "default.aurora-postgresql9.6"

  depends_on = [
    "data.external.secrets_processing" 
  ]
}