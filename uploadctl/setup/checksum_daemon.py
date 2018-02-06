import os

from proforma import CompositeComponent, ExternalControl
from proforma.aws import Lambda, IAMRole, RoleInlinePolicy


class ChecksumLambda(Lambda):
    def __init__(self, **options):
        super().__init__(name=f"upload-checksum-daemon-{os.environ['DEPLOYMENT_STAGE']}", **options)


class ChecksumLambdaRole(IAMRole):
    def __init__(self, **options):
        super().__init__(name=f"upload-checksum-daemon-{os.environ['DEPLOYMENT_STAGE']}",
                         trust_document=None,
                         **options)

    def set_it_up(self):
        raise ExternalControl("Use \"make deploy\" to set this up")


class ChecksumLambdaRolePolicy(RoleInlinePolicy):
    def __init__(self, **options):
        super().__init__(role_name=f"upload-checksum-daemon-{os.environ['DEPLOYMENT_STAGE']}",
                         name=f"upload-checksum-daemon-{os.environ['DEPLOYMENT_STAGE']}",
                         policy_document=None,
                         **options)

    def set_it_up(self):
        raise ExternalControl("Use \"make deploy\" to set this up")


class ChecksumDaemon(CompositeComponent):

    SUBCOMPONENTS = {
        'upload-checksum-lambda': ChecksumLambda,
        'upload-checksum-lambda-role': ChecksumLambdaRole,
        'upload-checksum-lambda-role-policy': ChecksumLambdaRolePolicy,
    }

    def __str__(self):
        return "Checksum daemon:"
