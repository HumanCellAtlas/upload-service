import os

from .lambda_mgr import LambdaMgr


class RunLevelCLI:

    @classmethod
    def configure(cls, subparsers):
        runlevel_parser = subparsers.add_parser('runlevel', description="Adjust Upload Run Level")
        runlevel_parser.set_defaults(command='runlevel')
        runlevel_subparsers = runlevel_parser.add_subparsers()

        status_parser = runlevel_subparsers.add_parser('status', description="Report Upload run status")
        status_parser.set_defaults(command='runlevel', runlevel_cmd='status')

    def __init__(self):
        self.deployment_stage = os.environ['DEPLOYMENT_STAGE']

    def run(self, args):
        if args.runlevel_cmd == 'status':
            self.status()

    def status(self):
        LambdaMgr.do_to_all(self.deployment_stage, 'status')
