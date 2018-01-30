#!/usr/bin/env python3.6

"""
Upload Service Administration Tool

    uploadctl setup|check|teardown   Manage cloud infrastructure
    uploadctl cleanup                Remove old upload areas
    uploadctl test                   Test Upload Service, run uploadctl test -h for more details
"""

import argparse
import os

from .amqp_tool import AmqpTool
from .setup.conductor import SetupConductor
from .upload_cleaner import UploadCleaner


class UploadctlCLI:

    def __init__(self):

        parser = self._setup_argparse()
        args = parser.parse_args()

        if 'command' not in args:
            parser.print_help()
            exit(1)

        if args.command == 'amqp':
            if args.amqp_command == 'listen':
                tool = AmqpTool(server=args.server, exchange_name=args.exchange, queue_name=args.queue_name)
                tool.create_queue()
                tool.listen()
            elif args.amqp_command == 'publish':
                tool = AmqpTool(server=args.server, exchange_name=args.exchange, queue_name=args.queue_name)
                tool.publish()
                exit(0)

        deployment = self._check_deployment(args)

        if args.command in ['setup', 'check', 'teardown']:
            if args.component:
                component = SetupConductor.SUBCOMPONENTS[args.component](**vars(args))
                getattr(component, args.command)()
            else:
                setup = SetupConductor(**vars(args))
                getattr(setup, args.command)()

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

        setup_parser = subparsers.add_parser('setup')
        setup_parser.set_defaults(command='setup')
        setup_parser.add_argument('component', nargs='?', choices=list(SetupConductor.SUBCOMPONENTS.keys()))
        setup_parser.add_argument('--ami', type=str, metavar="ID",
                                  help="AMI to use for validation batch compute env setup")
        setup_parser.add_argument('--ec2-key-pair', type=str, metavar="KEYNAME",
                                  help="Key pair to use for validation batch compute env setup")
        setup_parser.add_argument('--security-groups', type=str, metavar="GROUPS", default='default',
                                  help="Comma-separated list of EC2 security groups to use"
                                       " for validation batch compute env setup")

        check_parser = subparsers.add_parser('check')
        check_parser.set_defaults(command='check')
        check_parser.add_argument('component', nargs='?', choices=list(SetupConductor.SUBCOMPONENTS.keys()))

        teardown_parser = subparsers.add_parser('teardown')
        teardown_parser.set_defaults(command='teardown')
        teardown_parser.add_argument('component', nargs='?', choices=list(SetupConductor.SUBCOMPONENTS.keys()))

        test_parser = subparsers.add_parser('test', formatter_class=argparse.RawTextHelpFormatter,
                                            description="""Test Upload Service components:
        
        uploadctl test amqp listen|publish
        """)
        test_subparsers = test_parser.add_subparsers()

        amqp_parser = test_subparsers.add_parser('amqp', description="Test AMQP server")
        amqp_parser.set_defaults(command='amqp')
        amqp_parser.add_argument('amqp_command', choices=['publish', 'listen'])
        amqp_parser.add_argument('queue_name', nargs='?', default='ingest.sam.test')
        amqp_parser.add_argument('-e', '--exchange')
        amqp_parser.add_argument('-s', '--server')

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
