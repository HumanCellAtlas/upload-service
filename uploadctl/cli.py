#!/usr/bin/env python3.6

"""
Upload Service Administration Tool

    uploadctl setup|check|teardown   Manage cloud infrastructure
    uploadctl cleanup                Remove old upload areas
    uploadctl test                   Test Upload Service, run uploadctl test -h for more details
"""

import argparse
import os

from .setup import SetupCLI
from .test import TestCLI
from .upload_cleaner import UploadCleaner


class UploadctlCLI:

    def __init__(self):

        parser = self._setup_argparse()
        args = parser.parse_args()

        if 'command' not in args:
            parser.print_help()
            exit(1)

        deployment = self._check_deployment(args)

        if args.command in ['setup', 'check', 'teardown']:
            SetupCLI.run(args)

        if args.command == 'test':
            TestCLI.run(args)

        elif args.command == 'cleanup':
            UploadCleaner(deployment,
                          clean_older_than_days=args.age_days,
                          ignore_file_age=args.ignore_file_age,
                          dry_run=args.dry_run)

    @staticmethod
    def _setup_argparse():
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-d', '--deployment',
                            choices=['dev', 'integration', 'staging', 'prod'],
                            help="operate on this deployment")
        subparsers = parser.add_subparsers()

        cleanup_parser = subparsers.add_parser('cleanup', description="Remove old Upload Areas")
        cleanup_parser.set_defaults(command='cleanup')
        cleanup_parser.add_argument('--age-days', type=int, default=3, help="delete areas older than this")
        cleanup_parser.add_argument('--ignore-file-age', action='store_true', help="ignore age of files in bucket")
        cleanup_parser.add_argument('--dry-run', action='store_true', help="examine but don't take action")

        SetupCLI.configure(subparsers)
        TestCLI.configure(subparsers)
        return parser

    @staticmethod
    def _check_deployment(args):
        if not args.deployment:
            deployment = os.environ['DEPLOYMENT_STAGE']
            answer = input(f"Use deployment {deployment}? (y/n): ")
            if answer is not 'y':
                exit(1)
        else:
            deployment = args.deployment
            os.environ['DEPLOYMENT_STAGE'] = deployment
        return deployment
