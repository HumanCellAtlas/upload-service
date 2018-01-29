import os

from .component import CompositeComponent, ExternalControl
from .aws.llambda import Lambda
from .aws.iam import IAMRole, RoleInlinePolicy


class ApiLambda(Lambda):

    def __init__(self):
        super().__init__(name=f"upload-api-{os.environ['DEPLOYMENT_STAGE']}")


class ApiLambdaRole(IAMRole):
    def __init__(self):
        super().__init__(name=f"upload-api-{os.environ['DEPLOYMENT_STAGE']}", trust_document=None)

    def set_it_up(self):
        raise ExternalControl("Use \"make deploy\" to set this up")


class ApiLambdaRolePolicy(RoleInlinePolicy):
    def __init__(self):
        super().__init__(role_name=f"upload-api-{os.environ['DEPLOYMENT_STAGE']}",
                         name=f"upload-api-{os.environ['DEPLOYMENT_STAGE']}",
                         policy_document=None)

    def set_it_up(self):
        raise ExternalControl("Use \"make deploy\" to set this up")


class UploadApi(CompositeComponent):

    SUBCOMPONENTS = {
        'api-lambda': ApiLambda,
        'apl-lambda-role': ApiLambdaRole,
        'apl-lambda-role-policy': ApiLambdaRolePolicy,
    }

    def __str__(self):
        return "Upload API:"
