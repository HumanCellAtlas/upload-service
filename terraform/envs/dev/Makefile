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
