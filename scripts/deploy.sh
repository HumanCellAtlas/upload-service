#!/usr/bin/env bash

set -euo pipefail

if [[ $# != 1 ]]; then
    echo "Usage: $(basename $0) stage"
    exit 1
fi

export DEPLOYMENT_STAGE=$1
export SERVICE="upload"

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

function delete_all_job_definitions() {
    prefix="$SERVICE-$DEPLOYMENT_STAGE-"
    jobNames=$(aws batch describe-job-definitions | jq -r '.jobDefinitions[].jobDefinitionName' | grep $prefix)
    for jobName in $jobNames; do
        aws glue delete-job --job-name $jobName
        break
    done
}

source config/environment
echo "Deploying to ${DEPLOYMENT_STAGE}"
cd terraform/envs/${DEPLOYMENT_STAGE} && make init && cd ../../..
make db/migrate
make deploy
aws secretsmanager update-secret --secret-id="dcp/upload/${DEPLOYMENT_STAGE}/upload_service_version" --secret-string='{ "upload_service_version": "'${UPLOAD_SERVICE_VERSION}'" }'
delete_all_job_definitions

#if [ ${DEPLOYMENT_STAGE} != dev ] ; then
#    tag_deploy
#fi
