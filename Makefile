include common.mk
.PHONY: lint test unit-tests
MODULES=upload tests

test: lint unit-tests

lint:
	flake8 $(MODULES) *.py

unit-tests:
	PYTHONWARNINGS=ignore:ResourceWarning coverage run --source=upload \
		-m unittest discover --start-directory tests/unit --top-level-directory . --verbose

functional-tests:
	PYTHONWARNINGS=ignore:ResourceWarning python \
		-m unittest discover --start-directory tests/functional --top-level-directory . --verbose

clean clobber build deploy:
	$(MAKE) -C chalice $@
	$(MAKE) -C daemons $@

run: build
	scripts/upload-api

secrets:
	openssl enc -aes-256-cbc -k $(enc_password) -in config/deployment_secrets.${DEPLOYMENT_STAGE} -out config/deployment_secrets.${DEPLOYMENT_STAGE}.enc
