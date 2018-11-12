import os

from .lambda_mgr import LambdaMgr
from .batch_deployment_mgr import BatchDeploymentMgr


class RunLevelCLI:

    @classmethod
    def configure(cls, subparsers):
        runlevel_parser = subparsers.add_parser('runlevel', description="Adjust Upload Run Level")
        runlevel_parser.set_defaults(command='runlevel')
        runlevel_subparsers = runlevel_parser.add_subparsers()

        status_parser = runlevel_subparsers.add_parser('status', description="Report Upload run status")
        status_parser.set_defaults(command='runlevel', runlevel_cmd='status')

        stop_parser = runlevel_subparsers.add_parser('stop', description="Stop infrastructure")
        stop_parser.set_defaults(command='runlevel', runlevel_cmd='stop')

        start_parser = runlevel_subparsers.add_parser('start', description="Start infrastructure")
        start_parser.set_defaults(command='runlevel', runlevel_cmd='start')

    def __init__(self):
        self.deployment_stage = os.environ['DEPLOYMENT_STAGE']

    def run(self, args):
        if args.runlevel_cmd == 'status':
            self.status()
        elif args.runlevel_cmd == 'stop':
            self.stop()
        elif args.runlevel_cmd == 'start':
            self.start()

    def status(self):
        LambdaMgr.do_to_all(self.deployment_stage, 'status')
        BatchDeploymentMgr.do_to_all(self.deployment_stage, 'status')

    def stop(self):
        LambdaMgr.do_to_all(self.deployment_stage, 'stop')
        BatchDeploymentMgr.do_to_all(self.deployment_stage, 'stop')

    def start(self):
        LambdaMgr.do_to_all(self.deployment_stage, 'start')
        BatchDeploymentMgr.do_to_all(self.deployment_stage, 'start')
