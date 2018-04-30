export EXPORT_ENV_VARS_TO_LAMBDA=DEPLOYMENT_STAGE \
			BUCKET_NAME \
			INGEST_AMQP_SERVER \
			DCP_EVENTS_TOPIC \
			CSUM_DOCKER_IMAGE \
			CSUM_JOB_Q_ARN \
			CSUM_JOB_ROLE_ARN \
			API_HOST

clean:
	git clean -df .

clobber: clean
	git checkout .chalice/*.json

build:
	mkdir -p domovoilib/upload/common domovoilib/upload/lambdas
	cp -R ../../upload/__init__.py \
		  ../../upload/common \
		domovoilib/upload
	cp -R ../../upload/lambdas/__init__.py \
		  ../../upload/lambdas/common \
		  ../../upload/lambdas/checksum_daemon \
		domovoilib/upload/lambdas
	shopt -s nullglob; for wheel in vendor.in/*/*.whl; do unzip -q -o -d vendor $$wheel; done

deploy: build
	./build_deploy_config.sh upload-checksum-daemon $(DEPLOYMENT_STAGE)
	domovoi deploy --stage $(DEPLOYMENT_STAGE)
