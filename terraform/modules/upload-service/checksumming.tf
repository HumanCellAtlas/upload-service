resource "aws_batch_compute_environment" "csum_compute_env" {
  compute_environment_name = "dcp-upload-csum-cluster-${var.deployment_stage}"
  type = "MANAGED"
  service_role = "${aws_iam_role.AWSBatchServiceRole.arn}"
  compute_resources {
    type = "SPOT"
    bid_percentage = 100
    spot_iam_fleet_role = "${aws_iam_role.AmazonEC2SpotFleetRole.arn}"
    max_vcpus = 64
    min_vcpus = 0
    desired_vcpus = 0
    instance_type = [
      "m4"
    ]
    subnets = [
      "${data.aws_subnet.vpc.*.id}"
    ]
    security_group_ids = [
      "${var.vpc_default_security_group_id}"
    ]
    ec2_key_pair = "${var.csum_cluster_ec2_key_pair}"
    instance_role = "${aws_iam_instance_profile.ecsInstanceRole.arn}"
  }
  depends_on = [
    "aws_iam_role_policy_attachment.AWSBatchServiceRole"
  ]
}

resource "aws_batch_job_queue" "csum_job_q" {
  name = "dcp-upload-csum-q-${var.deployment_stage}"
  compute_environments = [
    "${aws_batch_compute_environment.csum_compute_env.arn}"]
  priority = 1
  state = "ENABLED"
}

resource "aws_iam_policy" "csum_job_policy" {
  name = "dcp-upload-csum-job-${var.deployment_stage}"
  policy = <<POLICY
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::${aws_s3_bucket.upload_areas_bucket.bucket}/*"
            ]
        }
    ]
}
POLICY
}

resource "aws_iam_role" "csum_job_role" {
  name = "dcp-upload-csum-job-${var.deployment_stage}"
  assume_role_policy = <<POLICY
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "Service": "ecs-tasks.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        },
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
POLICY
}

resource "aws_iam_role_policy_attachment" "csum_job_role" {
  role = "${aws_iam_role.csum_job_role.name}"
  policy_arn = "${aws_iam_policy.csum_job_policy.arn}"
}
