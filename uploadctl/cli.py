#!/usr/bin/env python3.7

"""
Upload Service Administration Tool

    uploadctl cleanup                Remove old upload areas
    uploadctl test                   Test Upload Service, run uploadctl test -h for more details
"""

import argparse
import os

from .cleanup import CleanupCLI
from .diagnostics import DiagnosticsCLI
from .runlevel import RunLevelCLI
from .test import TestCLI


class UploadctlCLI:

    def __init__(self):

        parser = self._setup_argparse()
        args = parser.parse_args()

        if 'command' not in args:
            parser.print_help()
            exit(1)

        elif args.command == 'diag':
            DiagnosticsCLI.run(args)
            exit(0)

        self._check_deployment(args)

        if args.command == 'runlevel':
            RunLevelCLI().run(args)

        elif args.command == 'test':
            TestCLI.run(args)

        elif args.command == 'cleanup':
            CleanupCLI.run(args)

        exit(0)

    @staticmethod
    def _setup_argparse():
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-d', '--deployment',
                            choices=['local', 'predev', 'dev', 'integration', 'staging', 'prod'],
                            help="operate on this deployment")
        subparsers = parser.add_subparsers()

        RunLevelCLI.configure(subparsers)
        CleanupCLI.configure(subparsers)
        DiagnosticsCLI.configure(subparsers)
        TestCLI.configure(subparsers)
        return parser

    @staticmethod
    def _check_deployment(args):
        if args.deployment:
            deployment = args.deployment
            os.environ['DEPLOYMENT_STAGE'] = deployment
        else:
            deployment = os.environ['DEPLOYMENT_STAGE']
            answer = input(f"Use deployment {deployment}? (y/n): ")
            if answer is not 'y':
                exit(1)
        return deployment
