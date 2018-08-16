import functools
import logging
import os
import traceback

import connexion
import flask
import requests
from connexion.resolver import RestyResolver
from connexion.lifecycle import ConnexionResponse

from upload.common.upload_config import UploadVersion
from ...common.exceptions import UploadException
from ...common.logging import get_logger
from ...common.logging import format_logger_with_id

get_logger('boto3').setLevel(logging.WARNING)
get_logger('botocore').setLevel(logging.WARNING)
get_logger('nose').setLevel(logging.WARNING)

logger = get_logger(__name__)


def create_app():
    app = connexion.App(__name__)
    resolver = RestyResolver("upload.api_server", collection_endpoint_name="list")
    swagger_spec_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config', 'upload-api.yml')
    app.add_api(swagger_spec_path, resolver=resolver, validate_responses=True)
    upload_service_version = UploadVersion().upload_service_version
    logger.warning("UPLOAD_SERVICE_VERSION: {}".format(upload_service_version))
    return app


def return_exceptions_as_http_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            _format_logger(kwargs)
            logger.info(f"Running {func} with args={args} kwargs={kwargs}")
            return func(*args, **kwargs)

        except UploadException as ex:
            status = ex.status
            title = ex.title
            detail = ex.detail

        except Exception as ex:
            status = requests.codes.server_error
            title = str(ex)
            detail = traceback.format_exc()

        error_response = rfc7807error_response(title, status, detail)
        logger.error(f"Returning rfc7807 error response: status={status}, title={title}, detail={detail}")
        return error_response

    return wrapper


def require_authenticated(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if 'INGEST_API_KEY' not in os.environ:
            raise UploadException(status=requests.codes.server_error,
                                  title="Authentication is not configured",
                                  detail="INGEST_API_KEY is not set.")
        api_key = connexion.request.headers.get('Api-Key', None)
        if api_key == os.environ['INGEST_API_KEY']:
            logger.info(f"Authenticated with Api-Key: {api_key[:3]}")
        else:
            raise UploadException(status=requests.codes.unauthorized,
                                  title="Access Denied.",
                                  detail=f"Unrecognized Api-Key: {api_key[:3]}...")
        return func(*args, **kwargs)

    return wrapper


RFC7807_MIMETYPE = 'application/problem+json'


def rfc7807error_response(title, status, detail=None):
    body = {
        'title': title,
        'status': status
    }
    if detail:
        body['detail'] = detail

    return ConnexionResponse(
        status_code=status,
        mimetype=RFC7807_MIMETYPE,
        content_type=RFC7807_MIMETYPE,
        body=body
    )


def _format_logger(kwargs):
    upload_area_id = kwargs.get("upload_area_id")
    filename = kwargs.get("filename")
    if upload_area_id:
        if filename:
            file_key = upload_area_id + "/" + filename
            format_logger_with_id(logger, "file_key", file_key)
        else:
            format_logger_with_id(logger, "upload_area_id", upload_area_id)
