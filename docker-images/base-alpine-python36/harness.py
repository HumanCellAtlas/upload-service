#!/usr/bin/env python

import argparse

from upload.docker_images.validator.validator_harness import ValidatorHarness

parser = argparse.ArgumentParser()
parser.add_argument('validator', help="Path of validator to invoke")
parser.add_argument('-t', '--test', action='store_true', help="Test only, do not submit results to Ingest")
parser.add_argument('-k', '--keep', action='store_true', help="Keep downloaded files after validation")
parser.add_argument('s3_url', metavar="<s3_url>", help="S3 URL of file to be validated")

args = parser.parse_args()

harness = ValidatorHarness(path_to_validator=args.validator, s3_url_of_file_to_be_validated=args.s3_url)
harness.validate(test_only=args.test)
