#!/bin/bash

set -euo pipefail

if [[ $# != 2 ]]; then
    echo "Usage: $(basename $0) daemon-name stage"
    exit 1
fi

export daemon_name=$1 stage=$2
export lambda_name="${daemon_name}-${stage}" iam_role_name="${daemon_name}-${stage}"
config_json=".chalice/config.json"
deployed_json=".chalice/deployed.json"
policy_template="${PROJECT_ROOT}/config/iam-policy-templates/${daemon_name}.json"
policy_json=".chalice/policy.json"
stage_policy_json=".chalice/policy-${stage}.json"

function update_env_in_config_json() {
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
    cat "$policy_template" | envsubst '$BUCKET_NAME_PREFIX $DEPLOYMENT_STAGE $account_id $stage $region_name' > "$policy_json"
    cp "$policy_json" "$stage_policy_json"
}

update_env_in_config_json
detect_existing_deployment
create_policy_document
