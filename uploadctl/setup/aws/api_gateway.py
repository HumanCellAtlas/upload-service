import os
import time

import boto3
from botocore.errorfactory import ClientError

from ..component import Component, ExternalControl
from .acm import SslCertificate


class RestApi(Component):

    def __init__(self, name, stage, **options):
        self.name = name
        self.stage_name = stage
        self.id = None
        self.apig = boto3.client('apigateway')
        self._load()
        super().__init__(**options)

    def __str__(self):
        return f"REST API {self.name}-{self.stage_name}"

    def is_setup(self):
        return self.id is not None

    def set_it_up(self):
        raise ExternalControl("Use \"make deploy\" to set this up")

    def tear_it_down(self):
        self.apig.delete_rest_api(restApiId=self.id)
        time.sleep(10)

    def _load(self):
        for rest_api in self.apig.get_rest_apis()['items']:
            if rest_api['name'] == self.name:
                for stage in self.apig.get_stages(restApiId=rest_api['id'])['item']:
                    if stage['stageName'] == self.stage_name:
                        self.id = rest_api['id']
                        return
        self.id = None


class DomainName(Component):

    def __init__(self, domain, **options):
        self.domain = domain
        super().__init__(**options)
        self.apig = boto3.client('apigateway')

    def __str__(self):
        return f"Custom domain name {self.domain}"

    def is_setup(self):
        try:
            self.apig.get_domain_name(domainName=self.domain)
            return True
        except ClientError:
            return False

    def set_it_up(self):
        wildcard_cert_domain = ".".join(['*'] + self.domain.split('.')[1:])
        cert = SslCertificate(domain=wildcard_cert_domain, quiet=True)
        self.apig.create_domain_name(
            domainName=self.domain,
            certificateName='string',
            certificateArn=cert.arn,
            endpointConfiguration={'types': ['EDGE']}
        )

    def tear_it_down(self):
        self.apig.delete_domain_name(domainName=self.domain)


class BasePathMapping(Component):

    def __init__(self, domain_name, base_path, rest_api_id, **options):
        self.domain_name = domain_name
        self.base_path = base_path
        self.rest_api_id = rest_api_id
        super().__init__(**options)
        self.apig = boto3.client('apigateway')

    def __str__(self):
        return f"Base path '{self.base_path}' mapping for domain {self.domain_name}"

    def is_setup(self):
        try:
            search_for = "(none)" if self.base_path == '' else self.base_path
            bpms = self.apig.get_base_path_mappings(domainName=self.domain_name)
            if 'items' in bpms:
                for item in bpms['items']:
                    if item['basePath'] == search_for and item['stage'] == os.environ['DEPLOYMENT_STAGE']:
                        return True
        except ClientError:
            pass
        return False

    def set_it_up(self):
        self.apig.create_base_path_mapping(
            domainName=self.domain_name,
            basePath=self.base_path,
            restApiId=self.rest_api_id,
            stage=os.environ['DEPLOYMENT_STAGE']
        )

    def tear_it_down(self):
        raise ExternalControl("Deleting the domain deletes this.")
        # self.apig.delete_base_path_mapping(
        #     domainName=self.domain_name,
        #     basePath=self.base_path,
        # )
        # Fails with:
        # botocore.exceptions.ClientError: An error occurred (403) when calling the DeleteBasePathMapping operation:
        # Unable to determine service/operation name to be authorized
