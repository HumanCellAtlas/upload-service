# Data Coordination Platform, Upload Service

[![Staging Service Build Status](https://travis-ci.org/HumanCellAtlas/upload-service.svg?branch=master)](https://travis-ci.org/HumanCellAtlas/upload-service)
[![CodeClimate Maintainability](https://api.codeclimate.com/v1/badges/4003ac7c053107137873/maintainability)](https://codeclimate.com/github/HumanCellAtlas/upload-service/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/4003ac7c053107137873/test_coverage)](https://codeclimate.com/github/HumanCellAtlas/upload-service/test_coverage)

## Overview

The DCP Upload Service provides a file staging and validation facility for the DCP.
Upload Areas are created/deleted using a REST API, which is secured so only the DCP Ingestion Service may use it.
It stages files into AWS S3 and computes checksums for the files.
The validation service runs Docker images against files.

## Components

### upload-api

Is a Lambda Chalice/Connexion/Flask app that presents the Upload Service REST API.
The API is defined using an OpenAPI 2.0 Specification (Swagger) in `config/upload-api.yml`.

### upload-checksum-daemon

Is a Lambda Domovoi app triggered by S3 ObjectCreated events that computes checksums for uploaded files.

### Validation Batch Service

Is an AWS Batch installation 

## Development Environment Setup

### Prerequisites

 - A Linux/Unix machine
 - git
 - Python 3.6

Check out the upload service repo:

```bash
# IMPORTANT use --recursive
git clone --recursive git@github.com:HumanCellAtlas/upload-service.git
cd upload-service
```

Install packages.  I use `virtualenv`, but you don’t have to.  This is what it looks for me:

```bash
mkdir venv  # I have venv/ in my global .gitignore
virtualenv --python python3.6 venv/36
source venv/36/bin/activate
pip install -r requirements-dev.txt
```

Do this once:

```bash
cp config/environment.dev.example config/environment.dev
```
Then edit as necessary.

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

## Validation Deployment

*UNDER CONSTRUCTION - NOTHING TO SEE HERE*

### Prerequisites

 * Create the validation AMI before deploying creating the Batch installation.
   See instructions in `validation/ami/README.md`.
 * Your VPC must have security groups named `default` and `inbound-ssh-from-hca-teams`.
 * Create IAM policy `upload-validator-<stage>` and role `upload-validator-<stage>`.
 * Have Docker installed and running on your local machine.

### Do It

```bash
scripts/batchctl.py staging setup

cd validation/docker-images/base-alpine-python36
make release
```
