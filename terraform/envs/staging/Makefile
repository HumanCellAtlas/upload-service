ifndef TERRAFORM_STATE_BUCKET
$(error Please export TERRAFORM_STATE_BUCKET to your environment)
endif

default: plan

init:
	terraform init --backend-config="bucket=$(TERRAFORM_STATE_BUCKET)" --backup=-

plan:
	terraform plan

apply:
	terraform apply

import:
	terraform import module.upload-service.aws_iam_role.AWSBatchServiceRole AWSBatchServiceRole

	terraform import module.upload-service.aws_iam_role.AWSServiceRoleForEC2Spot AWSServiceRoleForEC2Spot
	terraform import module.upload-service.aws_iam_role.AWSServiceRoleForEC2SpotFleet  AWSServiceRoleForEC2SpotFleet
	terraform import module.upload-service.aws_iam_role.AmazonEC2SpotFleetRole AmazonEC2SpotFleetRole

	terraform import module.upload-service.aws_iam_instance_profile.ecsInstanceRole ecsInstanceRole
	terraform import module.upload-service.aws_iam_role.ecsInstanceRole ecsInstanceRole
