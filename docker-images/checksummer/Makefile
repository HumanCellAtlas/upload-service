HUB_ORG=humancellatlas
IMAGE=upload-checksummer
VERSION=$(shell cat VERSION)

# Modus operandi
# --------------
# make build
#	test locally
# make release
#	test with explicit version number from Docker Hub
# make promote
#	promote that latest version to "latest"

build:
	rm -rf code/upload
	mkdir -p code/upload
	cp -R ../../upload/__init__.py ../../upload/common code/upload
	cp -R ../../upload/docker_images/checksummer/checksummer.py code
	docker build -t $(IMAGE):$(VERSION) .

examine:
	docker run -it --rm $(IMAGE):$(VERSION) /bin/bash

play:
	docker run -it --rm -v ~/.aws:/root/.aws -v `pwd`/checksummer.py:/checksummer.py $(IMAGE) /bin/bash

release: build bump_version push

push:
	$(eval VERSION=$(shell cat VERSION))
	docker tag $(IMAGE):$(VERSION) $(HUB_ORG)/$(IMAGE):$(VERSION)
	docker push $(HUB_ORG)/$(IMAGE):$(VERSION)

promote:
	$(eval VERSION=$(shell cat VERSION))
	docker tag $(IMAGE):$(VERSION) $(HUB_ORG)/$(IMAGE):latest
	docker push $(HUB_ORG)/$(IMAGE):latest

bump_version:
	expr `cat VERSION` + 1 > VERSION

test:
	docker run -it --rm -v ~/.aws:/root/.aws \
	--env CONTAINER=true \
	--env AWS_PROFILE=hca \
	--env API_HOST=upload.predev.data.humancellatlas.org \
	--env AWS_BATCH_JOB_ID=1 \
	--env CHECKSUM_ID=2 \
	--env AWS_BATCH_JOB_ATTEMPT=1 \
	$(IMAGE):$(VERSION) python /checksummer.py s3://org-humancellatlas-sam/even 342f31b73c44cbbd1dff188c4e881eed
	# The above hex number is tge s3_etag of the file to be checksummed.
	# The checksummer is now called with this so it can check the file has not changed since we schedule the job.

.phony: build bump_version examine play promote push release
