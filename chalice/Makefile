include ../common.mk

export EXPORT_ENV_VARS_TO_LAMBDA=DEPLOYMENT_STAGE \
			INGEST_API_KEY \
			INGEST_AMQP_SERVER \
			API_HOST

clean:
	git clean -df .

clobber: clean
	git checkout .chalice/*.json

build:
	cp ../requirements.txt .
	mkdir -p chalicelib/upload/common chalicelib/upload/lambdas
	cp -R ../upload/__init__.py \
		  ../upload/common \
		chalicelib/upload
	cp -R ../upload/lambdas/__init__.py \
		  ../upload/lambdas/api_server \
		chalicelib/upload/lambdas
	mkdir -p chalicelib/config
	envsubst '$$API_HOST' < ../config/upload-api.yml > chalicelib/config/upload-api.yml
	shopt -s nullglob; for wheel in vendor.in/*/*.whl; do unzip -q -o -d vendor $$wheel; done

deploy: clean build
	@echo -e "\n\n#########################################################"
	@echo -e "########## Deploying to $(DEPLOYMENT_STAGE) environment"
	@echo -e "#########################################################\n"
	./build_deploy_config.sh $(DEPLOYMENT_STAGE)
	chalice deploy --no-autogen-policy --stage $(DEPLOYMENT_STAGE) --api-gateway-stage $(DEPLOYMENT_STAGE)

