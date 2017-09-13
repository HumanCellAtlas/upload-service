include common.mk
.PHONY: tests
MODULES=staging tests

test: lint tests

lint:
	flake8 $(MODULES) *.py

tests:
	PYTHONWARNINGS=ignore:ResourceWarning coverage run --source=staging \
		-m unittest discover --start-directory tests --top-level-directory . --verbose

build:
	$(MAKE) -C chalice build

deploy:
	$(MAKE) -C chalice deploy

clean:
	$(MAKE) -C chalice clean

clobber:
	$(MAKE) -C chalice clobber

run: build
	scripts/staging-api
