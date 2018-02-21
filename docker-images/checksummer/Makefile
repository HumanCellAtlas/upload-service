HUB_ORG=humancellatlas
IMAGE=upload-checksummer

# Modus operandi
# --------------
# make build
#	test locally
# make release
#	test with explicit version number from Docker Hub
# make promote
#	promote that latest version to "latest"

build:
	mkdir -p code/upload
	cp -R ../../upload/__init__.py ../../upload/common code/upload
	cp -R ../../upload/docker_images/checksummer/checksummer.py code
	docker build -t $(IMAGE) .

examine:
	docker run -it --rm $(IMAGE) /bin/bash

play:
	docker run -it --rm -v ~/.aws:/root/.aws -v `pwd`/checksummer.py:/checksummer.py $(IMAGE) /bin/bash

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
