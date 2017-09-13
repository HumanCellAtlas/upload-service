# Human Cell Atlas, Data Coordination Platform, Staging System

[![Staging Service Build Status](https://travis-ci.org/HumanCellAtlas/staging-service.svg?branch=master)](https://travis-ci.org/HumanCellAtlas/staging-service)

## Overview

The HCA DCP Staging Service (HCASS) provides a file staging facility for the HCA.
It stages files into AWS S3 and computes chceksums for the files.
Staging Areas are created/deleted using a REST API, which is secured so only
the HCA DCP Ingestion Service may use it.

## Components

### staging-api

Is a Lambda Chalice/Connexion/Flask app that presents the HCASS REST API.
The API is defined using an OpenAPI 2.0 Specification (Swagger) in `config/staging-api.yml`. 

## Development Setup

Do this once:

```bash
cp config/environment.dev.example config/environment.dev
```
Then edit as necessary.

```bash
pip install -r requirements-dev.txt
```

## Running Tests

```bash
source config/environment
make test
```

## Running Locally
```bash
source config/environment
scripts/staging-api
```

## Deployment

Deployment is typically performed by Travis.

To manually deploy to e.g. staging:

```bash
DEPLOYMENT_STAGE=staging
source config/environment
make deploy
```
