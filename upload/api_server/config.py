import os
import requests

from . import return_exceptions_as_http_errors


@return_exceptions_as_http_errors
def client_config():
    config_info = {
        'upload_bucket_template': os.environ['BUCKET_NAME_TEMPLATE']
    }
    return config_info, requests.codes.ok
