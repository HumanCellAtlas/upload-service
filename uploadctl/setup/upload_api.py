import os

from preform import CompositeComponent, ExternalControl
from preform.aws import Lambda, IAMRole, RoleInlinePolicy, DomainName, BasePathMapping, RestApi, SslCertificate


class ApiLambda(Lambda):

    def __init__(self, **options):
        super().__init__(name=f"upload-api-{os.environ['DEPLOYMENT_STAGE']}", **options)


class ApiLambdaRole(IAMRole):
    def __init__(self, **options):
        super().__init__(name=f"upload-api-{os.environ['DEPLOYMENT_STAGE']}", trust_document=None, **options)

    def set_it_up(self):
        raise ExternalControl("Use \"make deploy\" to set this up")


class ApiLambdaRolePolicy(RoleInlinePolicy):
    def __init__(self, **options):
        super().__init__(role_name=f"upload-api-{os.environ['DEPLOYMENT_STAGE']}",
                         name=f"upload-api-{os.environ['DEPLOYMENT_STAGE']}",
                         policy_document=None,
                         **options)

    def set_it_up(self):
        raise ExternalControl("Use \"make deploy\" to set this up")


class ApiSSLCert(SslCertificate):
    def __init__(self, **options):
        wildcard_cert_domain = ".".join(['*'] + os.environ['API_HOST'].split('.')[1:])
        super().__init__(domain=wildcard_cert_domain, **options)


class ApiDomain(DomainName):
    def __init__(self, **options):
        super().__init__(domain=os.environ['API_HOST'], **options)


class UploadRestApi(RestApi):
    def __init__(self, **options):
        super().__init__(name='upload.api_server', stage=os.environ['DEPLOYMENT_STAGE'], **options)


class ApiBasePathMapping(BasePathMapping):
    def __init__(self, **options):
        rest_api = UploadRestApi(quiet=True)
        super().__init__(
            domain_name=os.environ['API_HOST'],
            base_path='',
            rest_api_id=rest_api.id,
            **options
        )


class UploadApi(CompositeComponent):

    SUBCOMPONENTS = {
        'api-lambda': ApiLambda,
        'apl-lambda-role': ApiLambdaRole,
        'apl-lambda-role-policy': ApiLambdaRolePolicy,
        'ssl-cert': ApiSSLCert,
        'rest-api': UploadRestApi,
        'custom-domain': ApiDomain,
        'base-path-mapping': ApiBasePathMapping,
    }

    def __str__(self):
        return "Upload API:"
