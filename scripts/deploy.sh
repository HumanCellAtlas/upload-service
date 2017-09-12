#!/usr/bin/env bash

source config/deployment_secrets.${DEPLOYMENT_STAGE}
make deploy
