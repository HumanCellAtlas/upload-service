HUB_ORG=humancellatlas
IMAGE=upload-validator-example
VERSION=$(shell cat VERSION)

# Modus operandi
# --------------
# make bump_version
#	make some changes
# make build
# make test
#	test locally
# make push
#	test with explicit version number from Docker Hub

build:
	docker build -t $(IMAGE):$(VERSION) .

examine:
	docker run -it --rm --entrypoint /bin/bash $(IMAGE):$(VERSION)

push:
	docker tag $(IMAGE):$(VERSION) $(HUB_ORG)/$(IMAGE):$(VERSION)
	docker push $(HUB_ORG)/$(IMAGE):$(VERSION)

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

.phony: build bump_version examine push test
