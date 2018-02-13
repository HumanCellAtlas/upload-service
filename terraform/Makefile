default: plan

init:
	cd envs/$(DEPLOYMENT_STAGE) && terraform init

plan:
	cd envs/$(DEPLOYMENT_STAGE) && terraform plan

apply:
	cd envs/$(DEPLOYMENT_STAGE) && terraform apply
