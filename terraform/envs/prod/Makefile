ifndef TERRAFORM_STATE_BUCKET
$(error Please export TERRAFORM_STATE_BUCKET to your environment)
endif

default: plan

init:
	terraform init --backend-config="bucket=$(TERRAFORM_STATE_BUCKET)"

plan:
	terraform plan

apply:
	terraform apply --backup=-

import:
	terraform import module.upload-service.aws_iam_role.AWSServiceRoleForEC2Spot      AWSServiceRoleForEC2Spot
	terraform import module.upload-service.aws_iam_role.AWSServiceRoleForEC2SpotFleet AWSServiceRoleForEC2SpotFleet
