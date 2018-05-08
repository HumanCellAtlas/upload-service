output "database_uri" {
  value = "postgresql://${aws_rds_cluster.upload.master_username}:${aws_rds_cluster.upload.master_password}@${aws_rds_cluster.upload.endpoint}/${aws_rds_cluster.upload.database_name}"
}
