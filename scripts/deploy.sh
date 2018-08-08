#!/usr/bin/env bash

set -euo pipefail

if [[ $# != 1 ]]; then
    echo "Usage: $(basename $0) stage"
    exit 1
fi

export DEPLOYMENT_STAGE=$1

# function tag_deploy(){
#    TAG=`date -u +"${DEPLOYMENT_STAGE}-%Y%m%dT%H%M%SZ"`
#    echo "Tagging deploy ${TAG}"
#    curl -X POST \
#         --header "Authorization: token ${GITHUB_ACCESS_TOKEN}" \
#         --header "Content-Type: application/json" \
#         --data @- \
#         https://api.github.com/repos/HumanCellAtlas/upload-service/git/refs <<-EOF
# {
#  "ref": "refs/tags/${TAG}",
#  "sha": "`git rev-parse HEAD`"
# }
# EOF
# }

source config/environment
echo "Deploying to ${DEPLOYMENT_STAGE}"
cd terraform/envs/${DEPLOYMENT_STAGE} && make init && cd ../../..
alembic -x db=${DEPLOYMENT_STAGE} -c=./config/database.ini upgrade head
make deploy

#if [ ${DEPLOYMENT_STAGE} != dev ] ; then
#    tag_deploy
#fi
