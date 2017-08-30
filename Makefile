export STAGE=dev
export STAGING_S3_BUCKET=org-humancellatlas-staging-$(STAGE)
export EXPORT_ENV_VARS_TO_LAMBDA=STAGING_S3_BUCKET
MODULES=staging tests

lint:
	flake8 $(MODULES) *.py

test: lint
	PYTHONWARNINGS=ignore:ResourceWarning coverage run --source=staging -m unittest discover tests -v

deploy: clean
	cp -R staging staging-api.yml chalicelib
	./build_deploy_config.sh $(STAGE)
	chalice deploy --no-autogen-policy --stage $(STAGE) --api-gateway-stage $(STAGE)

clean:
	git clean -df chalicelib

clobber: clean
	git checkout .chalice/*.json
