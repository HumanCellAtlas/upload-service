import boto3

from ..component import Component, ExternalControl


class SslCertificate(Component):

    def __init__(self, domain, **options):
        self.domain = domain
        self.arn = None
        super().__init__(**options)
        self.acm = boto3.client('acm')
        self._load_arn()

    def __str__(self):
        return f"SSL certificate {self.domain}"

    def is_setup(self):
        return self.arn is not None

    def set_it_up(self):
        raise ExternalControl("Please use AWS Cert Mgr to set this up")

    def tear_it_down(self):
        raise ExternalControl("Please use AWS Cert Mgr to manage this")

    def _load_arn(self):
        for summary in self.acm.list_certificates()['CertificateSummaryList']:
            if summary['DomainName'] == self.domain:
                self.arn = summary['CertificateArn']
                break
