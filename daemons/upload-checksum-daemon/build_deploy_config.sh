#!/bin/bash

set -euo pipefail

if [[ $# != 2 ]]; then
    echo "Usage: $(basename $0) daemon-name stage"
    exit 1
fi

export daemon_name=$1 stage=$2
export lambda_name="${daemon_name}-${stage}"
config_json=".chalice/config.json"
deployed_json=".chalice/deployed.json"
stage_policy_json=".chalice/policy-${stage}.json"

function update_config_json() {
    upload_csum_lambda_role_arn=`cd ${PROJECT_ROOT}/terraform/envs/${stage} ; terraform output upload_csum_lambda_role_arn`
    cat "$config_json" | jq ".iam_role_arn = \"${upload_csum_lambda_role_arn}\"" | sponge "$config_json"

    for var in ${EXPORT_ENV_VARS_TO_LAMBDA}; do
        cat "$config_json" | jq .stages.${stage}.environment_variables.${var}=env.${var} | sponge "$config_json"
    done
}

function detect_existing_deployment() {
    export lambda_arn=$(aws lambda list-functions | jq -r '.Functions[] | select(.FunctionName==env.lambda_name) | .FunctionArn')
    if [[ -z ${lambda_arn} ]]; then
        echo "Lambda function $lambda_name not found, resetting deploy config"
        rm -f "${deployed_json}"
    else
        jq -n ".${stage}.api_handler_name = env.lambda_name | \
               .${stage}.api_handler_arn = env.lambda_arn | \
               .${stage}.rest_api_id = \"\" | \
               .${stage}.region = env.AWS_DEFAULT_REGION | \
               .${stage}.api_gateway_stage = null | \
               .${stage}.backend = \"api_server\" | \
               .${stage}.chalice_version = \"1.0.1\" | \
               .${stage}.lambda_functions = {}" > "$deployed_json"
    fi
}

function create_policy_document() {
    # Fake out Domovoi, we are now managing policy with Terraform
    jq -n .Statement=\"\" > ${stage_policy_json}
}

update_config_json
detect_existing_deployment
create_policy_document
