#!/bin/bash

set -euo pipefail

get_api_id() {
    for api_id in $(aws apigateway get-rest-apis | jq -r .items[].id); do
        for resource_id in $(aws apigateway get-resources --rest-api-id $api_id | jq -r .items[].id); do
            aws apigateway get-integration --rest-api-id $api_id --resource-id $resource_id --http-method GET >/dev/null 2>&1 || continue
            uri=$(aws apigateway get-integration --rest-api-id $api_id --resource-id $resource_id --http-method GET | jq -r .uri)
            if [[ $uri == *"$lambda_arn"* ]]; then
                echo $api_id
                return
            fi
        done
    done
}

if [[ $# != 1 ]]; then
    echo "Usage: $(basename $0) stage"
    exit 1
fi

export stage=$1
deployed_json=".chalice/deployed.json"
config_json=".chalice/config.json"
policy_json=".chalice/policy.json"
stage_policy_json=".chalice/policy-${stage}.json"
export app_name=$(cat "$config_json" | jq -r .app_name)
policy_template="${SS_HOME}/iam/policy-templates/${app_name}-lambda.json"
export lambda_name="${app_name}-${stage}"
export region_name=$(aws configure get region)
export account_id=$(aws sts get-caller-identity | jq -r .Account)

cat "$config_json" | jq ".stages.$stage.api_gateway_stage=env.stage" | sponge "$config_json"

export lambda_arn=$(aws lambda list-functions | jq -r '.Functions[] | select(.FunctionName==env.lambda_name) | .FunctionArn')
if [[ -z $lambda_arn ]]; then
    echo "Lambda function $lambda_name not found, resetting Chalice config"
    rm -f "$deployed_json"
else
    export api_id=$(get_api_id)
    cat "$deployed_json" | jq .$stage.api_handler_arn=env.lambda_arn | jq .$stage.rest_api_id=env.api_id | sponge "$deployed_json"
fi

for var in $EXPORT_ENV_VARS_TO_LAMBDA; do
    cat "$config_json" | jq .stages.$stage.environment_variables.$var=env.$var | sponge "$config_json"
done

if [[ ${CI:-} == true ]]; then
    export iam_role_arn="arn:aws:iam::${account_id}:role/${lambda_name}"
    cat "$config_json" | jq .manage_iam_role=false | jq .iam_role_arn=env.iam_role_arn | sponge "$config_json"
fi

cat "$policy_template" | envsubst '$STAGING_S3_BUCKET $account_id $stage $region_name' > "$policy_json"
cp "$policy_json" "$stage_policy_json"
