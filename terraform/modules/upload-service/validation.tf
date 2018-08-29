data "external" "validation_desired_vcpus" {
  program = ["python", "${path.module}/fetch_batch_vcpus.py"]

  query = {
    compute_environment_name = "dcp-upload-validation-cluster-${var.deployment_stage}"
  }
}

resource "aws_batch_compute_environment" "validation_compute_env" {
  compute_environment_name = "dcp-upload-validation-cluster-${var.deployment_stage}"
  type = "MANAGED"
  service_role = "${aws_iam_role.AWSBatchServiceRole.arn}"
  compute_resources {
    type = "SPOT"
    bid_percentage = 100
    spot_iam_fleet_role = "${aws_iam_role.AmazonEC2SpotFleetRole.arn}"
    max_vcpus = 256
    min_vcpus = "${var.validation_cluster_min_vcpus}"
    // You must set desired_vcpus otherwise you get error: "desiredvCpus should be between minvCpus and maxvCpus"
    // However this is actually not settable in AWS.  It will not let you change it.
    // Here we use an external data source to dynamically set the desired vcpus to match current state.
    desired_vcpus = "${data.external.validation_desired_vcpus.result.desired_vcpus}"
    instance_type = [
      "m4"
    ]
    image_id = "${var.validation_cluster_ami_id}"
    subnets = [
      "${data.aws_subnet_ids.upload_vpc.ids}"
    ]
    security_group_ids = [
      "${module.upload-vpc.vpc_default_security_group_id}"
    ]
    ec2_key_pair = "${var.validation_cluster_ec2_key_pair}"
    instance_role = "${aws_iam_instance_profile.ecsInstanceRole.arn}"
    // Do not appear to work.  They do not stick.
    // tags {
    //   Name = "dcp-upload-validation-${var.deployment_stage}"
    // }
  }
  depends_on = [
    "aws_iam_role_policy_attachment.AWSBatchServiceRole"
  ]
}

resource "aws_batch_job_queue" "validation_job_q" {
  name = "dcp-upload-validation-q-${var.deployment_stage}"
  compute_environments = [
    "${aws_batch_compute_environment.validation_compute_env.arn}"]
  priority = 1
  state = "ENABLED"
}

resource "aws_iam_policy" "validation_job_policy" {
  name = "dcp-upload-validation-job-${var.deployment_stage}"
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

resource "aws_iam_role" "validation_job_role" {
  name = "dcp-upload-validation-job-${var.deployment_stage}"
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

resource "aws_iam_role_policy_attachment" "validation_job_role" {
  role = "${aws_iam_role.validation_job_role.name}"
  policy_arn = "${aws_iam_policy.validation_job_policy.arn}"
}
