import boto3

from ..component import Component, ExternalControl


class Lambda(Component):

    def __init__(self, name, **options):
        self.name = name
        super().__init__(**options)
        self.lamb = boto3.client('lambda')

    def __str__(self):
        return f"Lambda {self.name}"

    def is_setup(self):
        for function_name in self._lambda_functions():
            if function_name == self.name:
                return True
        return False

    def set_it_up(self):
        raise ExternalControl("Use \"make deploy\" to set this up")

    def tear_it_down(self):
        self.lamb.delete_function(FunctionName=self.name)

    def _lambda_functions(self):
        paginator = self.lamb.get_paginator('list_functions')
        for page in paginator.paginate(FunctionVersion='ALL'):
            if 'Functions' in page:
                for func in page['Functions']:
                    yield func['FunctionName']
