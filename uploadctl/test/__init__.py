import argparse
import os

import boto3

from .amqp_tool import AmqpTool
from upload.batch import JobDefinition
from ..setup.batch_validation import BatchValidationJobQueue
from .rest_api import RestApiTest


class TestCLI:

    @classmethod
    def configure(cls, subparsers):
        test_parser = subparsers.add_parser('test', formatter_class=argparse.RawTextHelpFormatter,
                                            description="""Test Upload Service components:

        uploadctl test amqp listen|publish
        uploadctl test api
        uploadctl test batch <docker-image>
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
        test_batch_parser.add_argument("image", metavar="IMAGE", help="Test Batch setup with this Docker image")
        test_batch_parser.add_argument("docker_command", nargs=argparse.REMAINDER,
                                       help="Command and arguments for Docker image")

        test_api_parser = test_subparsers.add_parser("api", description="Test REST API")
        test_api_parser.set_defaults(command='test', test_command='api')
        test_api_parser.add_argument('-v', '--verbose', action='store_true', help="Display response detail")
        test_api_parser.add_argument('-p', '--pause', action='store_true', help="Pause between steps")
        test_api_parser.add_argument('-u', '--uuid', nargs='?', help="Use this upload area ID")

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
            cls.test_batch_infrastructure(docker_image=args.image, command=args.docker_command)
        elif args.test_command == 'api':
            RestApiTest(verbose=args.verbose, pause=args.pause, uuid=args.uuid).run()
        exit(0)

    @classmethod
    def test_batch_infrastructure(cls, docker_image, command):
        batch = boto3.client('batch')
        account_id = boto3.client('sts').get_caller_identity().get('Account')
        job_role_arn = f"arn:aws:iam::{account_id}:role/upload-batch-job-{os.environ['DEPLOYMENT_STAGE']}"
        job_defn = JobDefinition(
            docker_image=docker_image,
            deployment=os.environ['DEPLOYMENT_STAGE']
        ).find_or_create(job_role_arn)
        jobq = BatchValidationJobQueue(quiet=True)
        jobq.is_setup()  # load arn
        response = batch.submit_job(
            jobName='test-job',
            jobQueue=jobq.arn,
            jobDefinition=job_defn.arn,
            containerOverrides={
                'command': command
            }
        )
        print(f"Submit job returned {response}")
