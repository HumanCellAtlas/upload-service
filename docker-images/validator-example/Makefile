HUB_ORG=humancellatlas
IMAGE=upload-validator-example
VERSION=$(shell cat VERSION)

# Modus operandi
# --------------
# make bump_version
#	make some changes
# make build
#	test locally
# make push
#	test with explicit version number from Docker Hub
# make promote
#	promote that latest version to "latest" on Docker Hub

build:
	docker build -t $(IMAGE):$(VERSION) .

examine:
	docker run -it --rm --entrypoint /bin/bash $(IMAGE):$(VERSION)

push:
	docker tag $(IMAGE):$(VERSION) $(HUB_ORG)/$(IMAGE):$(VERSION)
	docker push $(HUB_ORG)/$(IMAGE):$(VERSION)

promote:
	$(eval VERSION=$(shell cat VERSION))
	docker tag $(HUB_ORG)/$(IMAGE):$(VERSION) $(HUB_ORG)/$(IMAGE):latest
	docker push $(HUB_ORG)/$(IMAGE):latest

bump_version:
	expr `cat VERSION` + 1 > VERSION
	$(eval VERSION=$(shell cat VERSION))

test:
	docker run -it --rm -v ~/.aws:/root/.aws \
	--env CONTAINER=true \
	--env DEPLOYMENT_STAGE=test \
	--env AWS_PROFILE=hca \
	--env API_HOST=upload.predev.data.humancellatlas.org \
	--env AWS_BATCH_JOB_ID=1 \
	--env VALIDATION_ID=2 \
	--env AWS_BATCH_JOB_ATTEMPT=1 \
	$(IMAGE):$(VERSION) /validator s3://org-humancellatlas-sam/even

.phony: build bump_version examine promote push test
