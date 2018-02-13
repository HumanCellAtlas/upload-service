resource "aws_s3_bucket" "upload_areas_bucket" {
  bucket = "${var.bucket_name_prefix}${var.deployment_stage}"
  acl = "private"
  force_destroy = "false"
  acceleration_status = "Enabled"
}

