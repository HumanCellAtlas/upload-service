include ../common.mk

clean:
	git clean -df chalicelib

clobber: clean
	git clean -df .chalice
	git checkout .chalice/*.json

build:
	cp -R ../staging ../checksumming_io ../config/staging-api.yml chalicelib

deploy: clean build
	@echo -e "\n\n#########################################################"
	@echo -e "########## Deploying to $(DEPLOYMENT_STAGE) environment"
	@echo -e "#########################################################\n"
	./build_deploy_config.sh $(DEPLOYMENT_STAGE)
	chalice deploy --no-autogen-policy --stage $(DEPLOYMENT_STAGE) --api-gateway-stage $(DEPLOYMENT_STAGE)

