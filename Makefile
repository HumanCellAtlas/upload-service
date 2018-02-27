include common.mk
.PHONY: tests
MODULES=upload tests

test: lint tests

lint:
	flake8 $(MODULES) *.py

tests:
	PYTHONWARNINGS=ignore:ResourceWarning coverage run --source=upload \
		-m unittest discover --start-directory tests --top-level-directory . --verbose

clean clobber build deploy:
	$(MAKE) -C chalice $@
	$(MAKE) -C daemons $@

run: build
	scripts/upload-api

secrets:
	openssl enc -aes-256-cbc -k $(enc_password) -in config/deployment_secrets.dev     -out config/deployment_secrets.dev.enc
	openssl enc -aes-256-cbc -k $(enc_password) -in config/deployment_secrets.staging -out config/deployment_secrets.staging.enc
	openssl enc -aes-256-cbc -k $(enc_password) -in config/deployment_secrets.integration -out config/deployment_secrets.integration.enc
	openssl enc -aes-256-cbc -k $(enc_password) -in config/deployment_secrets.prod    -out config/deployment_secrets.prod.enc
