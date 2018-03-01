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

.phony: build bump_version examine promote push
