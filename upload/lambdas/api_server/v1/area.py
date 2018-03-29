import json
import urllib.parse

import connexion
import requests

from .. import return_exceptions_as_http_errors, require_authenticated
from ..validation import Validation
from ...common.event_notifier import EventNotifier
from ....common.upload_area import UploadArea
from ....common.exceptions import UploadException
from ....common.logging import get_logger


@return_exceptions_as_http_errors
@require_authenticated
def create(upload_area_id: str):
    upload_area = UploadArea(upload_area_id)
    if upload_area.is_extant():
        raise UploadException(status=requests.codes.conflict, title="Upload Area Already Exists",
                              detail=f"Upload area {upload_area_id} already exists.")
    upload_area.create()
    EventNotifier.notify(f"{upload_area_id} created")
    return {'urn': upload_area.urn}, requests.codes.created


@return_exceptions_as_http_errors
@require_authenticated
def delete(upload_area_id: str):
    upload_area = _load_upload_area(upload_area_id)
    upload_area.delete()
    EventNotifier.notify(f"{upload_area_id} deleted")
    return None, requests.codes.no_content


@return_exceptions_as_http_errors
@require_authenticated
def lock(upload_area_id: str):
    upload_area = _load_upload_area(upload_area_id)
    upload_area.lock()
    EventNotifier.notify(f"{upload_area_id} locked")
    return None, requests.codes.no_content


@return_exceptions_as_http_errors
@require_authenticated
def unlock(upload_area_id: str):
    upload_area = _load_upload_area(upload_area_id)
    upload_area.unlock()
    EventNotifier.notify(f"{upload_area_id} unlocked")
    return None, requests.codes.no_content


@return_exceptions_as_http_errors
@require_authenticated
def put_file(upload_area_id: str, filename: str, body: str):
    upload_area = _load_upload_area(upload_area_id)
    content_type = connexion.request.headers['Content-Type']
    fileinfo = upload_area.store_file(filename, content=body, content_type=content_type)
    EventNotifier.notify(f"{upload_area_id} {filename} added")
    return fileinfo, requests.codes.created


@return_exceptions_as_http_errors
@require_authenticated
def validate_file(upload_area_id: str, filename: str, json_request_body: str):
    upload_area = _load_upload_area(upload_area_id)
    file = upload_area.uploaded_file(urllib.parse.unquote(filename))
    body = json.loads(json_request_body)
    environment = body['environment'] if 'environment' in body else {}
    validation_id = Validation(file).schedule_validation(body['validator_image'], environment)
    EventNotifier.notify(f"{upload_area_id} validation of {filename} scheduled")
    return {'validation_id': validation_id}, requests.codes.ok


@return_exceptions_as_http_errors
def list_files(upload_area_id: str):
    upload_area = _load_upload_area(upload_area_id)
    EventNotifier.notify(f"{upload_area_id} listing files")
    return upload_area.ls(), requests.codes.ok


@return_exceptions_as_http_errors
def file_info(upload_area_id: str, filename: str):
    upload_area = _load_upload_area(upload_area_id)
    uploaded_file = upload_area.uploaded_file(filename)
    return uploaded_file.info(), requests.codes.ok


@return_exceptions_as_http_errors
def files_info(upload_area_id: str, body: str):
    filename_list = json.loads(body)
    upload_area = _load_upload_area(upload_area_id)
    response_data = []
    for filename in filename_list:
        uploaded_file = upload_area.uploaded_file(filename)
        response_data.append(uploaded_file.info())
    return response_data, requests.codes.ok


def _load_upload_area(upload_area_id: str):
    upload_area = UploadArea(upload_area_id)

    if not upload_area.is_extant():
        raise UploadException(status=requests.codes.not_found, title="Upload Area Not Found")
    return upload_area
