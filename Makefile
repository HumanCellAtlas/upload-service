export STAGING_S3_TEST_BUCKET=hca-staging-test
export EXPORT_ENV_VARS_TO_LAMBDA=STAGING_S3_TEST_BUCKET
export STAGE=dev
MODULES=staging tests

lint:
	flake8 $(MODULES) *.py

test: lint
	PYTHONWARNINGS=ignore:ResourceWarning coverage run --source=staging -m unittest discover tests -v

deploy:
	git clean -df chalicelib
	cp -R staging staging-api.yml chalicelib
	./build_deploy_config.sh $(STAGE)
	chalice deploy --no-autogen-policy --stage $(STAGE) --api-gateway-stage $(STAGE)
