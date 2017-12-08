import json

import connexion
import requests

from . import UploadException, return_exceptions_as_http_errors, require_authenticated
from .. import UploadArea, Validation


@return_exceptions_as_http_errors
@require_authenticated
def create(upload_area_id: str):
    upload_area = UploadArea(upload_area_id)
    if upload_area.is_extant():
        raise UploadException(status=requests.codes.conflict, title="Upload Area Already Exists",
                              detail=f"Upload area {upload_area_id} already exists.")
    upload_area.create()
    return {'urn': upload_area.urn}, requests.codes.created


@return_exceptions_as_http_errors
@require_authenticated
def delete(upload_area_id: str):
    upload_area = _load_upload_area(upload_area_id)
    upload_area.delete()
    return None, requests.codes.no_content


@return_exceptions_as_http_errors
@require_authenticated
def lock(upload_area_id: str):
    upload_area = _load_upload_area(upload_area_id)
    upload_area.lock()
    return None, requests.codes.no_content


@return_exceptions_as_http_errors
@require_authenticated
def unlock(upload_area_id: str):
    upload_area = _load_upload_area(upload_area_id)
    upload_area.unlock()
    return None, requests.codes.no_content


@return_exceptions_as_http_errors
@require_authenticated
def put_file(upload_area_id: str, filename: str, body: str):
    upload_area = _load_upload_area(upload_area_id)
    content_type = connexion.request.headers['Content-Type']
    fileinfo = upload_area.store_file(filename, content=body, content_type=content_type)
    return fileinfo, requests.codes.created


@return_exceptions_as_http_errors
@require_authenticated
def validate_file(upload_area_id: str, filename: str, json_request_body: str):
    upload_area = _load_upload_area(upload_area_id)
    file = upload_area.uploaded_file(filename)
    body = json.loads(json_request_body)
    environment = body['environment'] if 'environment' in body else {}
    validation_id = Validation(file).schedule_validation(body['validator_image'], environment)
    return {'validation_id': validation_id}, requests.codes.ok


@return_exceptions_as_http_errors
def list_files(upload_area_id: str):
    upload_area = _load_upload_area(upload_area_id)
    return upload_area.ls(), requests.codes.ok


def _load_upload_area(upload_area_id: str):
    upload_area = UploadArea(upload_area_id)

    if not upload_area.is_extant():
        raise UploadException(status=requests.codes.not_found, title="Upload Area Not Found")
    return upload_area
