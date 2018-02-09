export EXPORT_ENV_VARS_TO_LAMBDA=DEPLOYMENT_STAGE BUCKET_NAME INGEST_AMQP_SERVER DCP_EVENTS_TOPIC

clean:
	git clean -df .

clobber: clean
	git checkout .chalice/*.json

build:
	mkdir -p domovoilib
	cp -R ../../upload domovoilib
	shopt -s nullglob; for wheel in vendor.in/*/*.whl; do unzip -q -o -d vendor $$wheel; done

deploy: build
	./build_deploy_config.sh upload-checksum-daemon $(DEPLOYMENT_STAGE)
	domovoi deploy --stage $(DEPLOYMENT_STAGE)
