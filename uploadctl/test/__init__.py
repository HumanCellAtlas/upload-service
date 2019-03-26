import argparse
import os

from .amqp_tool import AmqpTool
from .batch import TestBatch


class TestCLI:

    @classmethod
    def configure(cls, subparsers):
        test_parser = subparsers.add_parser('test', formatter_class=argparse.RawTextHelpFormatter,
                                            description="""Test Upload Service components:

        uploadctl test amqp listen|publish
        uploadctl test batch <docker-image> <command>
        """)
        test_subparsers = test_parser.add_subparsers()

        amqp_parser = test_subparsers.add_parser('amqp', description="Test AMQP server")
        amqp_parser.set_defaults(command='test', test_command='amqp')
        amqp_parser.add_argument('amqp_command', choices=['publish', 'listen'])
        amqp_parser.add_argument('queue_name', nargs='?', default='ingest.sam.test')
        amqp_parser.add_argument('-e', '--exchange')
        amqp_parser.add_argument('-s', '--server')

        test_batch_parser = test_subparsers.add_parser("batch", description="Test Batch infrastructure")
        test_batch_parser.set_defaults(command='test', test_command='batch')
        test_batch_parser.add_argument("--queue", metavar="QUEUE_NAME", default=TestBatch.DEFAULT_QUEUE,
                                       help=f"Batch queue name (default={TestBatch.DEFAULT_QUEUE})")
        test_batch_parser.add_argument("--role", metavar="ROLE_NAME", default=TestBatch.DEFAULT_ROLE,
                                       help=f"Job role name (default={TestBatch.DEFAULT_ROLE})")
        test_batch_parser.add_argument("-e", "--env", metavar="X=Y", action="append")

        test_batch_parser.add_argument("image", metavar="IMAGE", help="Run this Docker image")
        test_batch_parser.add_argument("docker_command", nargs=argparse.REMAINDER,
                                       help="Command and arguments for Docker image")

    @classmethod
    def run(cls, args):
        if args.test_command == 'amqp':
            if args.amqp_command == 'listen':
                tool = AmqpTool(server=args.server, exchange_name=args.exchange, queue_name=args.queue_name)
                tool.create_queue()
                tool.listen()
            elif args.amqp_command == 'publish':
                tool = AmqpTool(server=args.server, exchange_name=args.exchange, queue_name=args.queue_name)
                tool.publish()

        elif args.test_command == 'batch':
            TestBatch(queue_name=args.queue,
                      role_name=args.role).run(docker_image=args.image,
                                               command=args.docker_command,
                                               env=args.env)
        exit(0)
