
ZIP_FILE := checksum_daemon.zip
TARGET := target/$(ZIP_FILE)

default: build

.PHONY: install
install:
	virtualenv -p python3 venv
	. venv/bin/activate && pip install -r requirements.txt --upgrade


.PHONY: build
build:
	rm -rf target
	mkdir target
	virtualenv -p python3 venv
	. venv/bin/activate && pip install -r requirements.txt -t target/ --upgrade

	cp -R build/* target/
	cp -R vendor/* target/
	cp -R vendor.in/* target/
	cp -R ../../upload target/
	cp -R *.py target/


	cd target && zip -r ../$(ZIP_FILE) *

.PHONY: deploy
deploy:
	. venv/bin/activate && terraform apply \
		-var-file $(PROJECT_ROOT)/terraform.tfvars \
		-var "target_zip_path=$(TARGET)" \
		-auto-approve