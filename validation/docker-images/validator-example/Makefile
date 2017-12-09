HUB_ORG=humancellatlas
IMAGE=upload-validator-example

build:
	docker build -t $(IMAGE) .

examine:
	docker run -it --rm --entrypoint /bin/bash $(IMAGE)

release: build bump_version push

push:
	$(eval VERSION=$(shell cat VERSION))
	docker tag $(IMAGE):latest $(HUB_ORG)/$(IMAGE):$(VERSION)
	docker tag $(IMAGE):latest $(HUB_ORG)/$(IMAGE):latest
	docker push $(HUB_ORG)/$(IMAGE):$(VERSION)
	docker push $(HUB_ORG)/$(IMAGE):latest

bump_version:
	expr `cat VERSION` + 1 > VERSION

.phony: build bump_version examine push release
