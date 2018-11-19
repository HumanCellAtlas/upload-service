import boto3

from .infra_mgr import InfraMgr


class LambdaMgr(InfraMgr):

    UPLOAD_LAMBDAS = [
        'upload-api-{env}',
        'dcp-upload-csum-{env}',
        'dcp-upload-batch-watcher-{env}',
        # 'dcp-upload-health-check-{env}' - leave this running
    ]

    @classmethod
    def do_to_all(cls, deployment_stage, action):
        print("Lambdas:")
        for lambda_name_template in cls.UPLOAD_LAMBDAS:
            lambda_name = lambda_name_template.format(env=deployment_stage)
            lambda_mgr = cls(lambda_name)
            action_function = getattr(lambda_mgr, action)
            print("  " + action_function())

    def __init__(self, lambda_name):
        self._lambda_name = lambda_name
        self._aws_lambda = boto3.client('lambda')

    def status(self):
        lambda_info = self._aws_lambda.get_function(FunctionName=self._lambda_name)
        if 'Concurrency' in lambda_info and lambda_info['Concurrency']['ReservedConcurrentExecutions'] == 0:
            state = "DOWN"
        else:
            state = 'UP'
        return "%-40s %s" % (lambda_info['Configuration']['FunctionName'], state)

    def stop(self):
        self._aws_lambda.put_function_concurrency(
            FunctionName=self._lambda_name,
            ReservedConcurrentExecutions=0
        )
        return self.status()

    def start(self):
        self._aws_lambda.delete_function_concurrency(
            FunctionName=self._lambda_name
        )
        return self.status()
