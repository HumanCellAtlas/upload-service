import boto3

from .infra_mgr import InfraMgr


class BatchQueueMgr:

    QUEUE_STATE_TO_RUN_STATE = {
        'ENABLED': 'UP',
        'DISABLED': 'DOWN'
    }

    def __init__(self, deployment_stage, deployment_prefix):
        self.deployment_stage = deployment_stage
        self._deployment_prefix = deployment_prefix
        self._queue_name = "{prefix}-q-{env}".format(prefix=self._deployment_prefix, env=self.deployment_stage)
        self._aws_batch = boto3.client('batch')

    def status(self):
        queue_info = self._aws_batch.describe_job_queues(jobQueues=[self._queue_name])
        queue_status = queue_info['jobQueues'][0]['state']
        queue_run_status = self.QUEUE_STATE_TO_RUN_STATE.get(queue_status, "?")
        return "%-40s %s (%s)" % (self._queue_name, queue_run_status, queue_status)

    def stop(self):
        self._aws_batch.update_job_queue(jobQueue=self._queue_name, state='DISABLED')
        return self.status()

    def start(self):
        self._aws_batch.update_job_queue(jobQueue=self._queue_name, state='ENABLED')
        return self.status()


class BatchClusterMgr:

    CLUSTER_STATE_TO_RUN_STATE = {
        'ENABLED': 'UP',
        'DISABLED': 'DOWN'
    }

    def __init__(self, deployment_stage, deployment_prefix):
        self.deployment_stage = deployment_stage
        self._deployment_prefix = deployment_prefix
        self._cluster_name = "{prefix}-cluster-{env}".format(prefix=self._deployment_prefix, env=self.deployment_stage)
        self._aws_batch = boto3.client('batch')

    def status(self):
        cluster_info = self._aws_batch.describe_compute_environments(computeEnvironments=[self._cluster_name])
        cluster_status = cluster_info['computeEnvironments'][0]['state']
        cluster_run_status = self.CLUSTER_STATE_TO_RUN_STATE.get(cluster_status, "?")
        return "%-40s %s (%s)" % (self._cluster_name, cluster_run_status, cluster_status)

    def stop(self):
        self._aws_batch.update_compute_environment(computeEnvironment=self._cluster_name, state='DISABLED')
        return self.status()

    def start(self):
        self._aws_batch.update_compute_environment(computeEnvironment=self._cluster_name, state='ENABLED')
        return self.status()


class BatchDeploymentMgr(InfraMgr):

    UPLOAD_BATCH_DEPLOYMENTS = [
        'dcp-upload-csum',
        'dcp-upload-validation'
    ]

    @classmethod
    def do_to_all(cls, deployment_stage, action):
        print("Batch:")
        for deployment_prefix in cls.UPLOAD_BATCH_DEPLOYMENTS:
            print(f"  {deployment_prefix}:")
            batch_mgr = cls(deployment_stage, deployment_prefix)
            action_function = getattr(batch_mgr, action)
            action_function()

    def __init__(self, deployment_stage, deployment_prefix):
        self.deployment_stage = deployment_stage
        self._deployment_prefix = deployment_prefix
        self._queue_mgr = BatchQueueMgr(deployment_stage, deployment_prefix)
        self._cluster_mgr = BatchClusterMgr(deployment_stage, deployment_prefix)

    def status(self):
        print("    " + self._queue_mgr.status())
        print("    " + self._cluster_mgr.status())

    def stop(self):
        print("    " + self._queue_mgr.stop())
        print("    " + self._cluster_mgr.stop())

    def start(self):
        print("    " + self._queue_mgr.start())
        print("    " + self._cluster_mgr.start())

