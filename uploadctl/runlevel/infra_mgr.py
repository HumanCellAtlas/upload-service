class InfraMgr:
    """
    Base class for classes that knows how to start/stop/get status of AWS infra.
    """

    @classmethod
    def do_to_all(cls, deployment_stage, action):
        raise NotImplementedError()

    def status(self):
        raise NotImplementedError()
