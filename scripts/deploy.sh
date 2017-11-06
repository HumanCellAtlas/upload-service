#!/usr/bin/env bash

if [[ $# != 1 ]]; then
    echo "Usage: $(basename $0) stage"
    exit 1
fi

export DEPLOYMENT_STAGE=$1

function load_secrets(){
    secrets_file="config/deployment_secrets.${DEPLOYMENT_STAGE}"
    if [ ! -f ${secrets_file} ] ; then
        openssl aes-256-cbc -k ${enc_password} -in ${secrets_file}.enc -out ${secrets_file} -d
    fi
    source ${secrets_file}
}

function tag_deploy(){
    curl -X POST \
         --header "Authorization: token ${GITHUB_ACCESS_TOKEN}" \
         --header "Content-Type: application/json" \
         --data @- \
         https://api.github.com/repos/HumanCellAtlas/upload-service/git/refs <<-EOF
{
  "ref": "`date -u +"refs/tags/${DEPLOYMENT_STAGE}-%Y%m%dT%H%M%SZ"`",
  "sha": "`git rev-parse HEAD`"
}
EOF
}

source config/environment
load_secrets
make deploy
if [ ${DEPLOYMENT_STAGE} != dev ] ; then
    tag_deploy
fi
