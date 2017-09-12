#!/bin/bash
#API_URL=http://localhost:5000/v1
API_URL=https://staging.dev.data.humancellatlas.org/v1
STAGING_AREA_ID=deadbeef-dead-dead-dead-beeeeeeeeeef

function pause() {
    echo
    echo -n "Press enter to continue..."
    read junk
    echo
}

function waiting() {
    echo -n "Waiting 10 seconds for IAM policy to take effect..."
    sleep 10
    echo "done."
}

function get_cred() {
    cred=$1
    python -c "\
import sys, json, base64 ; \
response = open('/tmp/response').read() ; \
encoded_creds = json.loads(response)['urn'].split(':')[4] ; \
creds = json.loads(base64.b64decode(encoded_creds)) ; \
sys.stdout.write(creds['${cred}'])"
}

function run_curl() {
    curl_command=$*
    echo curl ${curl_command}
    curl --silent --dump-header /tmp/header --output /tmp/response -H "Api-Key: ${INGEST_API_KEY}" ${curl_command}
    head -1 /tmp/header
    cat /tmp/response
}

function create() {
    echo "CREATE:"
    run_curl -X POST "${API_URL}/area/${STAGING_AREA_ID}"
    aws_access_key_id=`get_cred AWS_ACCESS_KEY_ID`
    aws_secret_access_key=`get_cred AWS_SECRET_ACCESS_KEY`
    echo AWS_ACCESS_KEY_ID=${aws_access_key_id}
    echo AWS_SECRET_ACCESS_KEY=${aws_secret_access_key}
}

function upload() {
    echo "UPLOAD TO S3:"
    echo aws s3 cp staging-api.yml s3://org-humancellatlas-staging-dev/${STAGING_AREA_ID}/
    env AWS_ACCESS_KEY_ID=${aws_access_key_id} AWS_SECRET_ACCESS_KEY=${aws_secret_access_key} aws s3 cp staging-api.yml s3://org-humancellatlas-staging-dev/${STAGING_AREA_ID}/
}

function put_file() {
    echo "PUT FILE VIA API:"
    echo curl -X PUT -H \"Content-type: application/json\" -d 'sdfjdsllfds' "${API_URL}/area/${STAGING_AREA_ID}/foobar2.json"
    curl --silent --dump-header /tmp/header --output /tmp/response  \
         -X PUT \
         -H "Api-Key: ${INGEST_API_KEY}" \
         -H "Content-type: application/json" \
         -d 'sdfjdsllfds' \
         "${API_URL}/area/${STAGING_AREA_ID}/foobar2.json"
    head -1 /tmp/header
    cat /tmp/response
}

function list() {
    echo "LIST FILES:"
    echo curl "${API_URL}/area/${STAGING_AREA_ID}"
    curl --silent "${API_URL}/area/${STAGING_AREA_ID}"
}

function lock() {
    echo "LOCK:"
    run_curl -X POST "${API_URL}/area/${STAGING_AREA_ID}/lock"
}

function unlock() {
    echo "UNLOCK:"
    run_curl -X DELETE "${API_URL}/area/${STAGING_AREA_ID}/lock"
}

function delete() {
    echo "DELETE:"
    run_curl -X DELETE "${API_URL}/area/${STAGING_AREA_ID}"
}

if [[ "${INGEST_API_KEY}" == "" ]] ; then
    echo "Please set INGEST_API_KEY"
    exit 1
fi

create ; waiting; pause
upload ; pause
put_file ; pause
list ; pause
lock ; waiting ; pause
echo "PROVE AREA IS LOCKED:"
upload ; pause
unlock ; waiting ; pause
upload ; pause
delete
