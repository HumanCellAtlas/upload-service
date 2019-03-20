HUB_ORG=humancellatlas
IMAGE=upload-validator-base-alpine
VERSION=$(shell cat VERSION)

# Modus operandi
# --------------
# make bump_version
#	make some changes
# make build
#	test locally:
#		In validator-example/
#		temporarily change Dockerfile to build on upload-validator-base-alpine:<new-version>
#		make build
#		make test
#		watch the output, look for payload with 'stdout': 'valid\n'
# make push
#	test with explicit version number from Docker Hub

build:
	mkdir -p code/upload code/upload/docker_images
	cp -R ../../upload/__init__.py ../../upload/common code/upload
	cp -R ../../upload/docker_images/validator code/upload/docker_images
	docker build -t $(IMAGE):$(VERSION) .

examine:
	docker run -it --rm --entrypoint /bin/bash $(IMAGE):$(VERSION)

play:
	docker run -it --rm -v ~/.aws:/root/.aws -v `pwd`/harness.py:/harness.py --entrypoint /bin/bash $(IMAGE):$(VERSION)

push:
	docker tag $(IMAGE):$(VERSION) $(HUB_ORG)/$(IMAGE):$(VERSION)
	docker push $(HUB_ORG)/$(IMAGE):$(VERSION)

bump_version:
	expr `cat VERSION` + 1 > VERSION
	$(eval VERSION=$(shell cat VERSION))

.phony: build bump_version examine play push
