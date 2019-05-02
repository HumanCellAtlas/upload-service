DEPLOYMENT_STAGE=staging
TF_STATE_BUCKET=org-humancellatlas-upload-infra
S3_TFVARS_FILE=s3://$(TF_STATE_BUCKET)/terraform/envs/$(DEPLOYMENT_STAGE)/terraform.tfvars

default: plan

init:
	terraform init

plan: retrieve-vars
	terraform plan -detailed-exitcode

apply: retrieve-vars
	terraform apply --backup=-

destroy: state/rm
	terraform destroy --backup=-

retrieve-vars:
	aws s3 cp $(S3_TFVARS_FILE) terraform.tfvars

upload-vars:
	aws s3 cp terraform.tfvars $(S3_TFVARS_FILE)

import:
	# These resources are shared between deployments in the same account
	- terraform import module.upload-service.aws_iam_service_linked_role.AWSServiceRoleForEC2Spot arn:aws:iam::861229788715:role/aws-service-role/spot.amazonaws.com/AWSServiceRoleForEC2Spot
	- terraform import module.upload-service.aws_iam_service_linked_role.AWSServiceRoleForEC2SpotFleet arn:aws:iam::861229788715:role/aws-service-role/spotfleet.amazonaws.com/AWSServiceRoleForEC2SpotFleet

state/rm:
	# These resources are shared between deployments in the same account
	- terraform state rm module.upload-service.aws_iam_service_linked_role.AWSServiceRoleForEC2Spot
	- terraform state rm module.upload-service.aws_iam_service_linked_role.AWSServiceRoleForEC2SpotFleet
