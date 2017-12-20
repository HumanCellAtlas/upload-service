import functools
import logging
import os
import traceback

import connexion
import flask
import requests
from connexion.resolver import RestyResolver
from connexion.lifecycle import ConnexionResponse

from .. import UploadException

logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('nose').setLevel(logging.WARNING)


def get_logger():
    try:
        return flask.current_app.logger
    except RuntimeError:
        return logging.getLogger(__name__)


def create_app():
    app = connexion.App(__name__)
    resolver = RestyResolver("upload.api_server", collection_endpoint_name="list")
    app.add_api('../../config/upload-api.yml', resolver=resolver, validate_responses=True)
    return app


def return_exceptions_as_http_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            get_logger().info(f"Running {func} with args={args} kwargs={kwargs}")
            return func(*args, **kwargs)

        except UploadException as ex:
            status = ex.status
            title = ex.title
            detail = ex.detail

        except Exception as ex:
            status = requests.codes.server_error
            title = str(ex)
            detail = traceback.format_exc()

        return rfc7807error_response(title, status, detail)

    return wrapper


def require_authenticated(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if 'INGEST_API_KEY' not in os.environ:
            raise UploadException(status=requests.codes.server_error,
                                  title="Authentication is not configured",
                                  detail="INGEST_API_KEY is not set.")
        api_key = connexion.request.headers.get('Api-Key', None)
        if not api_key == os.environ['INGEST_API_KEY']:
            raise UploadException(status=requests.codes.unauthorized, title="Access Denied.")
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
