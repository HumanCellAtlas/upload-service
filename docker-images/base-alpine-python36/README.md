# Upload Service Validation Docker Image Base

This docker image provides a base on which people can develop data file validators.

It contains a Docker `ENTRYPOINT` that runs a harness script that:

 * stages the file to be validated under /data
 * runs the validator
 * collects results and communicates them to the Upload API

## Building a Validator on this Base

To build a validator that uses this base, construct a Dockerfile like this:

```Dockerfile
FROM humancellatlas/upload-validator-base-alpine:<version>

# Install packages needed by your validator.

# Install your validator at /validator:
ADD myvalidator /validator
RUN chmod +x /validator
```

## How it Works

The Docker container will be invoked by the Upload Service:
 * with the command: `/validator s3://location/of/file-to-be-validated`
 * and with environment variables `DEPLOYMENT_STAGE`, `VALIDATION_ID`, `API_HOST`, and `CONTAINER`

The harness script intercepts execution then:
 * Stages the file to be validated under `/data`.
 * Invokes the validation script with `/validator /data/location/of/file-to-be-validated`.
 * Captures STDOUT, STDERR and the validator return code.
 * Sends this captured into to the Upload API.
 * Removes this copy of the file to be validated.

## Testing Your Validator Locally

Create your Docker image. Place a test file to be validated in a bucket in S3.
Build and invoke the validator with Docker.

As we're not running in AWS right now, you need to grant the container
permission to access yur bucket by providing environment variables
AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY. Alternatively you can mount
your AWS credentials in the container with option `-v ~/.aws:/root/.aws`.

The `-t` option is passed into the container.  It tells the harness not
to attempt to contact Ingest.

```bash
docker build -t myvalidator .

docker run --rm -e VALIDATION_ID=1 -e DEPLOYMENT_STAGE=dev \
           -e AWS_BATCH_JOB_ID=500 -e AWS_BATCH_JOB_ATTEMPT=1 -e CONTAINER=docker \
           API_HOST=upload.dev.data.humancellatlas.org -v ~/.aws:/root/.aws \
           my-validator -t /validator s3://mubucket/somefile
```

## Testing a Validator in the Upload Service Development Environment (DCP Developers Only)

1. Publish your validator Docker image, e.g. to Docker Hub.
2. Create an upload area and upload a file to it.
3. Use the Swagger UI or `curl` to initiate validation.  Here is the `curl` version:

```
curl -X PUT -H "Api-Key: look-it-up" \
            -H "content-type: application/json" \
            -d '{"validator_image": "my-docker-hub-acct/myvalidator"}' \
            https://upload.dev.data.humancellatlas.org/v1/area/<uuid>/<filename>/validate
```
4. Use the AWS Batch UI to find your job and look at its logs.

## Notes for Upload Development Team

The primary user of this Docker image is the DCP Ingest team's `fastq_utils`
docker image.  To update their image to use a newer version of this base
image, update the first line of its [Dockerfile](https://github.com/HumanCellAtlas/fastq_utils/blob/master/Dockerfile#L1):
```
FROM humancellatlas/upload-validator-base-alpine:19
```
Then submit a PR.

For reference, the version of the validator image used in each environment
is set [here](https://github.com/HumanCellAtlas/ingest-validator/blob/master/config/default.json#L53).
