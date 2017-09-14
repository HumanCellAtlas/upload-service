#!/usr/bin/env bash

if [[ $# != 1 ]]; then
    echo "Usage: $(basename $0) stage"
    exit 1
fi

export DEPLOYMENT_STAGE=$1
source config/environment
openssl aes-256-cbc -k $enc_password -in config/deployment_secrets.${DEPLOYMENT_STAGE}.enc -out config/deployment_secrets.${DEPLOYMENT_STAGE} -d
source config/deployment_secrets.${DEPLOYMENT_STAGE}
make deploy
