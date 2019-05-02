locals {
  namespace = "dcp-upload-${var.deployment_stage}"
}


resource "aws_iam_instance_profile" "ecsInstanceRole" {
  name = "${local.namespace}-ecsInstanceRole"
  role = "${aws_iam_role.ecsInstanceRole.name}"
}

resource "aws_iam_role" "ecsInstanceRole" {
  name = "${local.namespace}-ecsInstanceRole"
  path = "/"
  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy_attachment" "ecsInstanceRole" {
  role = "${aws_iam_role.ecsInstanceRole.name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_role" "AWSBatchServiceRole" {
  name = "${local.namespace}-AWSBatchServiceRole"
  path = "/service-role/"
  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "batch.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy_attachment" "AWSBatchServiceRole" {
  role = "${aws_iam_role.AWSBatchServiceRole.name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

resource "aws_iam_role" "AmazonEC2SpotFleetRole" {
  name = "${local.namespace}-AmazonEC2SpotFleetRole"
  path = "/"
  description = "Role to Allow EC2 Spot Fleet to request and terminate Spot Instances on your behalf."
  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "",
      "Effect": "Allow",
      "Principal": {
        "Service": "spotfleet.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy_attachment" "AmazonEC2SpotFleetRole" {
  role = "${aws_iam_role.AmazonEC2SpotFleetRole.name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetRole"
}

resource "aws_iam_service_linked_role" "AWSServiceRoleForEC2Spot" {
  aws_service_name = "spot.amazonaws.com"
  description = "Allows EC2 Spot to launch and manage spot instances."
}

resource "aws_iam_service_linked_role" "AWSServiceRoleForEC2SpotFleet" {
  aws_service_name = "spotfleet.amazonaws.com"
  description = "Default EC2 Spot Fleet Service Linked Role"
}
