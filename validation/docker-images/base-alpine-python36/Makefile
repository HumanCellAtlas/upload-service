HUB_ORG=humancellatlas
IMAGE=upload-validator-base-alpine

# Modus operandi
# --------------
# make build
#	test locally
# make release
#	test with explicit version number from Docker Hub
# make promote
#	promote that latest version to "latest"

build:
	docker build -t $(IMAGE) .

examine:
	docker run -it --rm --entrypoint /bin/bash $(IMAGE)

play:
	docker run -it --rm -v ~/.aws:/root/.aws -v `pwd`/harness.py:/harness.py --entrypoint /bin/bash $(IMAGE)

release: build bump_version push

push:
	$(eval VERSION=$(shell cat VERSION))
	docker tag $(IMAGE):latest $(HUB_ORG)/$(IMAGE):$(VERSION)
	docker push $(HUB_ORG)/$(IMAGE):$(VERSION)

promote:
	$(eval VERSION=$(shell cat VERSION))
	docker tag $(IMAGE):latest $(HUB_ORG)/$(IMAGE):latest
	docker push $(HUB_ORG)/$(IMAGE):latest

bump_version:
	expr `cat VERSION` + 1 > VERSION

.phony: build bump_version examine play promote push release
