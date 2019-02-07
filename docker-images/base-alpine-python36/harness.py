#!/usr/bin/env python

import argparse

from upload.docker_images.validator.validator_harness import ValidatorHarness

parser = argparse.ArgumentParser()
parser.add_argument('validator', help="Path of validator to invoke")
parser.add_argument('-t', '--test', action='store_true', help="Test only, do not submit results to Ingest")
parser.add_argument('-k', '--keep', action='store_true', help="Keep downloaded files after validation")
parser.add_argument('s3_urls', nargs=argparse.REMAINDER, help="S3 URLs of file/s to be validated")

args = parser.parse_args()

harness = ValidatorHarness(path_to_validator=args.validator, s3_urls_of_files_to_be_validated=args.s3_urls)
harness.validate(test_only=args.test)
