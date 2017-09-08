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
	cp -R staging staging-api.yml chalicelib

deploy:
	$(MAKE) -C .chalice deploy

clean:
	$(MAKE) -C .chalice clean

clobber:
	$(MAKE) -C .chalice clobber

run: build
	$(MAKE) -C chalice build
	./staging-api
