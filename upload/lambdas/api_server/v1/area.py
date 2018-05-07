import json
import urllib.parse
import connexion
import requests
from .. import return_exceptions_as_http_errors, require_authenticated
from ..validation_scheduler import ValidationScheduler
from ....common.upload_area import UploadArea
from ....common.checksum_event import UploadedFileChecksumEvent
from ....common.validation_event import UploadedFileValidationEvent
from ....common.exceptions import UploadException
from ....common.ingest_notifier import IngestNotifier
from ....common.logging import get_logger

logger = get_logger(__name__)


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
def schedule_file_validation(upload_area_id: str, filename: str, json_request_body: str):
    upload_area = _load_upload_area(upload_area_id)
    file = upload_area.uploaded_file(urllib.parse.unquote(filename))
    body = json.loads(json_request_body)
    environment = body['environment'] if 'environment' in body else {}
    validation_id = ValidationScheduler(file).schedule_validation(body['validator_image'], environment)
    return {'validation_id': validation_id}, requests.codes.ok


@return_exceptions_as_http_errors
def update_checksum_event(upload_area_id: str, checksum_id: str, body: str):
    _load_upload_area(upload_area_id)
    body = json.loads(body)
    status = body["status"]
    job_id = body["job_id"]
    payload = body["payload"]
    file_name = payload["name"]
    file_key = f"{upload_area_id}/{file_name}"

    checksum_event = UploadedFileChecksumEvent(file_id=file_key, checksum_id=checksum_id, job_id=job_id, status=status)
    if checksum_event.status == "CHECKSUMMED":
        checksum_event.checksums = payload["checksums"]
        _notify_ingest(payload, "file_uploaded")
    checksum_event.update_record()

    return None, requests.codes.no_content


@return_exceptions_as_http_errors
def update_validation_event(upload_area_id: str, validation_id: str, body: str):
    _load_upload_area(upload_area_id)
    body = json.loads(body)
    status = body["status"]
    job_id = body["job_id"]
    payload = body["payload"]
    file_name = payload["name"]
    file_key = f"{upload_area_id}/{file_name}"

    validation_event = UploadedFileValidationEvent(file_id=file_key,
                                                   validation_id=validation_id,
                                                   job_id=job_id,
                                                   status=status)
    if validation_event.status == "VALIDATED":
        validation_event.results = payload
        _notify_ingest(payload, "file_validated")
    validation_event.update_record()

    return None, requests.codes.no_content


@return_exceptions_as_http_errors
def list_files(upload_area_id: str):
    upload_area = _load_upload_area(upload_area_id)
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


def _notify_ingest(payload, notification_type):
    status = IngestNotifier(notification_type).format_and_send_notification(payload)
    logger.info(f"Notified Ingest: payload={payload}, status={status}")
