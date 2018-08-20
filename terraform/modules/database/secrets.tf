
resource "aws_secretsmanager_secret" "database-secrets" {
  name = "dcp/upload/${var.deployment_stage}/database"
}

resource "aws_secretsmanager_secret_version" "database-secrets" {
  secret_id = "${aws_secretsmanager_secret.database-secrets.id}"
  secret_string = <<SECRETS_JSON
{
  "database_uri": "postgresql://${aws_rds_cluster.upload.master_username}:${aws_rds_cluster.upload.master_password}@${aws_rds_cluster.upload.endpoint}/${aws_rds_cluster.upload.database_name}",
  "pgbouncer_uri": "postgresql://${aws_rds_cluster.upload.master_username}:${aws_rds_cluster.upload.master_password}@${aws_lb.main.dns_name}/${aws_rds_cluster.upload.database_name}"
}
SECRETS_JSON

  depends_on = [ "aws_ecs_service.pgbouncer" ]
}
