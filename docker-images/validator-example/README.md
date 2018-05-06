# DCP Upload Validation Service, Example Validator

The DCP Upload Service provides the ability to run a validator against uploaded files. 

This is a simple example validator that declares files with an even number of bytes valid,
and files with an odd number of bytes invalid.

## Validators

Validators are Docker images.
  
  - They should be derivatives of one of the "base" validator images.
  - They should have an executable file at `/validator`.
  - The validator will be called with a single argument, the location in
    the filesystem of the file to be validated.
  - Environment variables VALIDATION_ID and DEPLOYMENT_STAGE will be set.

When the validator image is run, the validator will be invoked with a single
argument: the path to a file to be validated.

The return code and output (STDOUT and STDERR) of the validator will be captured and sent
to the Ingest service.

## Base Images

The current list of base images is:

  - `upload-validator-base-alpine` - an Imaged derived from python:alpine3.6

Base images based on other distributions and versions can be generated upon request.

## Testing this Validator Locally

1. Create the validator Docker image.
2. Place a test file to be validated in a bucket in S3.
3. Invoke the validator with Docker.

As we're not running in AWS right now, you need to grant the container
permission to access yur bucket by providing environment variables
AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY. Alternatively you can mount
your AWS credentials in the container with option `-v ~/.aws:/root/aws`.

The `-t` option is passed into the container.  It tells the harness not
to attempt to contact Ingest. 

```bash
make build

aws s3 cp somefile s3://mybucket/

docker run --rm -e VALIDATION_ID=1 -e DEPLOYMENT_STAGE=dev \
           -e AWS_BATCH_JOB_ID=500 -e AWS_BATCH_JOB_ATTEMPT=1 -e CONTAINER=docker \
           API_HOST=upload.dev.data.humancellatlas.org -v ~/.aws:/root/.aws \
           upload-validator-example -t /validator s3://mubucket/somefile
```

## Testing a Validator in the Upload Service Development Environment (DCP Developers Only)

1. Publish the validator Docker image to Docker Hub.
2. Create an upload area and upload a file to it.
3. Use the Swagger UI or `curl` to initiate validation.  Here is the `curl` version:

```bash
make release

curl -X PUT -H "Api-Key: look-it-up" \
            -H "content-type: application/json" \
            -d '{"validator_image": "humancellatlas/upload-validator-example"}' \
            https://upload.dev.data.humancellatlas.org/v1/area/<uuid>/<filename>/validate
```

4. Use the AWS Batch UI to find your job and look at its logs.
