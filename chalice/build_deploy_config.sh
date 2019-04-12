#!/bin/bash

set -euo pipefail

api_gateway_name="upload.lambdas.api_server"

function setup_deployed_json() {
    deployed_json=".chalice/deployed.json"
    if [[ -z $lambda_arn ]]; then
        echo "Lambda function $lambda_name not found, resetting Chalice config"
        rm -f "$deployed_json"
    else
        export api_id=$(../scripts/get_api_id "$api_gateway_name" "$lambda_name")
        echo "API Gateway ID = ${api_id}"
        cat "$deployed_json" | jq .$stage.api_handler_arn=env.lambda_arn | jq .$stage.rest_api_id=env.api_id | sponge "$deployed_json"
    fi
}

function setup_config_json() {
    cat "$config_json" | jq ".stages.$stage.api_gateway_stage=env.stage" | sponge "$config_json"

    for var in ${EXPORT_ENV_VARS_TO_LAMBDA}; do
        echo "Adding environment variable ${var} to config"
        cat "$config_json" | jq .stages.$stage.environment_variables.$var=env.$var | sponge "$config_json"
    done

    if [[ ${CI:-} == true ]]; then
        export iam_role_arn="arn:aws:iam::${account_id}:role/${lambda_name}"
        cat "$config_json" | jq .manage_iam_role=false | jq .iam_role_arn=env.iam_role_arn | sponge "$config_json"
    fi
}

function setup_policy_json() {
    policy_json=".chalice/policy.json"
    stage_policy_json=".chalice/policy-${stage}.json"
    policy_template="${PROJECT_ROOT}/config/iam-policy-templates/${app_name}-lambda.json"
    cat "$policy_template" | envsubst '$DEPLOYMENT_STAGE $BUCKET_NAME $account_id' > "$policy_json"
    cp "$policy_json" "$stage_policy_json"
}

if [[ $# != 1 ]]; then
    echo "Usage: $(basename $0) stage"
    exit 1
fi

export stage=$1
config_json=".chalice/config.json"
export app_name=$(cat "$config_json" | jq -r .app_name)
export lambda_name="${app_name}-${stage}"
export region_name=$(aws configure get region)
export account_id=$(aws sts get-caller-identity | jq -r .Account)
export lambda_arn=$(aws lambda list-functions | jq -r '.Functions[] | select(.FunctionName==env.lambda_name) | .FunctionArn')
echo "app_name=${app_name}"
echo "lambda_name=${lambda_name}"
echo "lambda_arn=${lambda_arn}"

setup_deployed_json
setup_config_json
setup_policy_json
