import requests

from upload.common.upload_config import UploadVersion
from upload.lambdas.api_server import return_exceptions_as_http_errors


@return_exceptions_as_http_errors
def version():
    upload_service_version = UploadVersion().upload_service_version
    return {'upload_service_version': upload_service_version}, requests.codes.ok
