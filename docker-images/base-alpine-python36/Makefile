HUB_ORG=humancellatlas
IMAGE=upload-validator-base-alpine
VERSION=$(shell cat VERSION)

# Modus operandi
# --------------
# make bump_version
#   Make some changes
# make build
#	test locally
# make push
#	test with explicit version number from Docker Hub
# make promote
#	promote that latest version to "latest"

build:
	mkdir -p code/upload
	cp -R ../../upload/__init__.py ../../upload/common code/upload
	docker build -t $(IMAGE):$(VERSION) .

examine:
	docker run -it --rm --entrypoint /bin/bash $(IMAGE):$(VERSION)

play:
	docker run -it --rm -v ~/.aws:/root/.aws -v `pwd`/harness.py:/harness.py --entrypoint /bin/bash $(IMAGE):$(VERSION)

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

.phony: build bump_version examine play promote push
