export EXPORT_ENV_VARS_TO_LAMBDA=DEPLOYMENT_STAGE UPLOAD_SERVICE_S3_BUCKET

clean:
	git clean -df .

clobber: clean
	git checkout .chalice/*.json

build:
	mkdir -p domovoilib
	cp -R ../../upload ../../checksumming_io domovoilib

deploy: build
	./build_deploy_config.sh upload-checksum-daemon $(DEPLOYMENT_STAGE)
	domovoi deploy --stage $(DEPLOYMENT_STAGE)
