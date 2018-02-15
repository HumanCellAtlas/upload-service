#!/usr/bin/env bash

if [[ $# != 1 ]]; then
    echo "Usage: $(basename $0) stage"
    exit 1
fi

export DEPLOYMENT_STAGE=$1

function load_secrets(){
    secrets_file="config/deployment_secrets.${DEPLOYMENT_STAGE}"
    if [ ! -f ${secrets_file} ] ; then
        echo "Decrypting ${secrets_file}.enc"
        openssl aes-256-cbc -k ${enc_password} -in ${secrets_file}.enc -out ${secrets_file} -d
    fi
    echo "Loading ${secrets_file}"
    source ${secrets_file}
}

function tag_deploy(){
    TAG=`date -u +"${DEPLOYMENT_STAGE}-%Y%m%dT%H%M%SZ"`
    echo "Tagging deploy ${TAG}"
    curl -X POST \
         --header "Authorization: token ${GITHUB_ACCESS_TOKEN}" \
         --header "Content-Type: application/json" \
         --data @- \
         https://api.github.com/repos/HumanCellAtlas/upload-service/git/refs <<-EOF
{
  "ref": "refs/tags/${TAG}",
  "sha": "`git rev-parse HEAD`"
}
EOF
}

function install_terraform() {
    echo "Installing Terraform..."
    mkdir ./external_binaries
    curl https://releases.hashicorp.com/terraform/0.11.3/terraform_0.11.3_linux_amd64.zip -o /tmp/terraform.zip
    unzip /tmp/terraform.zip -d ./external_binaries/
    rm /tmp/terraform.zip
    export PATH=$PATH:`pwd`/external_binaries
    (cd terraform/envs/${DEPLOYMENT_STAGE} && terraform init -backend-config="bucket=${TERRAFORM_STATE_BUCKET}")
    which terraform
}

source config/environment
echo "Deploying to ${DEPLOYMENT_STAGE}"
load_secrets
install_terraform
make deploy
if [ ${DEPLOYMENT_STAGE} != dev ] ; then
    tag_deploy
fi
