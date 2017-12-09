# Data Coordination Platform, Upload Service

[![Staging Service Build Status](https://travis-ci.org/HumanCellAtlas/upload-service.svg?branch=master)](https://travis-ci.org/HumanCellAtlas/upload-service)
[![CodeClimate Maintainability](https://api.codeclimate.com/v1/badges/4003ac7c053107137873/maintainability)](https://codeclimate.com/github/HumanCellAtlas/upload-service/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/4003ac7c053107137873/test_coverage)](https://codeclimate.com/github/HumanCellAtlas/upload-service/test_coverage)

## Overview

The DCP Upload Service provides a file staging facility for the DCP.
It stages files into AWS S3 and computes checksums for the files.
Upload Areas are created/deleted using a REST API, which is secured so only the DCP Ingestion Service may use it.

## Components

### upload-api

Is a Lambda Chalice/Connexion/Flask app that presents the Upload Service REST API.
The API is defined using an OpenAPI 2.0 Specification (Swagger) in `config/upload-api.yml`.

### upload-checksum-daemon

Is a Lambda Domovoi app triggered by S3 ObjectCreated events that computes checksums for uploaded files.

### Validation Batch Service

Is an AWS Batch installation 

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
scripts/upload-api
```

## Deployment

Deployment is typically performed by Travis.

To manually deploy to e.g. the staging deployment:

```bash
export enc_password="<password-used-to-encrypt-deployment-secrets>"
scripts/deploy.sh staging
```

### Validation Deployment

#### Prerequisites

 * Create the validation AMI before deploying creating the Batch installation.
   See instructions in `validation/ami/README.md`.
 * Your VPC must have security groups named `default` and `inbound-ssh-from-hca-teams`.
 * Create IAM policy `upload-validator-<stage>` and role `upload-validator-<stage>`.
 * Have Docker installed and running on your local machine.

#### Do It

```bash
scripts/batchctl.py staging setup

cd validation/docker-images/base-alpine-python36
make release
```
