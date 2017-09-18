#!/usr/bin/env bash

if [[ $# != 1 ]]; then
    echo "Usage: $(basename $0) stage"
    exit 1
fi

function tag_deploy(){
    curl -X POST \
         --header "Authorization: token ${GITHUB_ACCESS_TOKEN}" \
         --header "Content-Type: application/json" \
         --data @- \
         https://api.github.com/repos/HumanCellAtlas/staging-service/git/refs <<-EOF
{
  "ref": "`date -u +"refs/tags/${DEPLOYMENT_STAGE}-%Y%m%dT%H%M%SZ"`",
  "sha": "`git rev-parse HEAD`"
}
EOF
}

export DEPLOYMENT_STAGE=$1
source config/environment
openssl aes-256-cbc -k $enc_password -in config/deployment_secrets.${DEPLOYMENT_STAGE}.enc -out config/deployment_secrets.${DEPLOYMENT_STAGE} -d
source config/deployment_secrets.${DEPLOYMENT_STAGE}
make deploy
tag_deploy
