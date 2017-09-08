include ../common.mk

clean:
	git clean -df ../chalicelib

clobber: clean
	git clean -df .
	git checkout *.json

build:
	cp -R ../staging ../staging-api.yml ../chalicelib

deploy: clean build
	@echo -e "\n\n#########################################################"
	@echo -e "########## Deploying to $(DEPLOYMENT_STAGE) environment"
	@echo -e "#########################################################\n"
	./build_deploy_config.sh $(DEPLOYMENT_STAGE)
	cd .. ; chalice deploy --no-autogen-policy --stage $(DEPLOYMENT_STAGE) --api-gateway-stage $(DEPLOYMENT_STAGE)

