.PHONY: tests
export STAGE=dev
export STAGING_S3_BUCKET=org-humancellatlas-staging-$(STAGE)
export EXPORT_ENV_VARS_TO_LAMBDA=STAGING_S3_BUCKET
MODULES=staging tests

test: lint tests

lint:
	flake8 $(MODULES) *.py

tests:
	PYTHONWARNINGS=ignore:ResourceWarning coverage run --source=staging \
		-m unittest discover --start-directory tests --top-level-directory . --verbose

build:
	cp -R staging staging-api.yml chalicelib

deploy: clean build
	./build_deploy_config.sh $(STAGE)
	chalice deploy --no-autogen-policy --stage $(STAGE) --api-gateway-stage $(STAGE)

clean:
	git clean -df chalicelib

clobber: clean
	git clean -df .chalice
	git checkout .chalice/*.json

run: build
	./staging-api
