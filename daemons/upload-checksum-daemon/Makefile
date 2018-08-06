
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

	cp -R vendor.in/* target/

	cp -R ../../upload target/
	cp -R *.py target/
	# build.zip contains the psycopg2-3.6 package downloaded from https://github.com/jkehler/awslambda-psycopg2
	# and renamed psycopg2
	unzip build.zip
	cp -R build/ target/
	rm -rf build
	shopt -s nullglob; for wheel in vendor.in/*/*.whl; do unzip -q -o -d vendor $$wheel; done

	cp -R vendor/* target/

	cd target && zip -r ../$(ZIP_FILE) *

.PHONY: deploy
deploy: build
	aws s3 cp $(ZIP_FILE) s3://org-humancellatlas-upload-checksum-lambda-deployment/$(DEPLOYMENT_STAGE)/$(ZIP_FILE)
	aws lambda update-function-code --function-name dcp-upload-csum-$(DEPLOYMENT_STAGE) --s3-bucket org-humancellatlas-upload-checksum-lambda-deployment --s3-key $(DEPLOYMENT_STAGE)/$(ZIP_FILE)
