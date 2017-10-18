include ../common.mk

export EXPORT_ENV_VARS_TO_LAMBDA=UPLOAD_SERVICE_S3_BUCKET DEPLOYMENT_STAGE INGEST_API_KEY

clean:
	git clean -df .

clobber: clean
	git checkout .chalice/*.json

build:
	cp ../requirements.txt .
	cp -R ../upload ../checksumming_io chalicelib
	mkdir -p chalicelib/config
	cp ../config/upload-api.yml chalicelib/config
	shopt -s nullglob; for wheel in vendor.in/*/*.whl; do unzip -q -o -d vendor $$wheel; done

deploy: clean build
	@echo -e "\n\n#########################################################"
	@echo -e "########## Deploying to $(DEPLOYMENT_STAGE) environment"
	@echo -e "#########################################################\n"
	./build_deploy_config.sh $(DEPLOYMENT_STAGE)
	chalice deploy --no-autogen-policy --stage $(DEPLOYMENT_STAGE) --api-gateway-stage $(DEPLOYMENT_STAGE)

