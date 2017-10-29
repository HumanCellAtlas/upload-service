#!/bin/bash

source "$(dirname $0)/../config/environment"

set -euo pipefail

if [[ $# != 2 ]]; then
    echo "Given an IAM principal intended to be used by a test/CI/CD pipeline,"
    echo "this script grants the principal the AWS IAM permissions necessary to"
    echo "test and deploy the application. Run this script using privileged"
    echo "(IAM write access) IAM credentials."
    echo "Usage: $(basename $0) iam-principal-type iam-principal-name"
    echo "Example: $(basename $0) user hca-test"
    exit 1
fi

export iam_principal_type=$1 iam_principal_name=$2
export region_name=$(aws configure get region)
export account_id=$(aws sts get-caller-identity | jq -r .Account)
envsubst_vars='$UPLOAD_SERVICE_BUCKET_PREFIX DEPLOYMENT_STAGE $region_name $account_id'

for policy_json in $(dirname $0)/../iam/policy-templates/ci-cd-*.json ; do

    policy_name=dcp-upload-`basename "${policy_json}"|sed 's/.json//'`
    echo "Applying policy ${policy_name} to ${iam_principal_type} ${iam_principal_name}..."
    aws iam put-${iam_principal_type}-policy \
        --${iam_principal_type}-name ${iam_principal_name} \
        --policy-name "${policy_name}" \
        --policy-document file://<(cat "$policy_json" | \
                                       envsubst "$envsubst_vars" | \
                                       jq -c 'del(.Statement[].Sid)')
done
