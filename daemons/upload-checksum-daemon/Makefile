export EXPORT_ENV_VARS_TO_LAMBDA=DEPLOYMENT_STAGE BUCKET_NAME_PREFIX

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
