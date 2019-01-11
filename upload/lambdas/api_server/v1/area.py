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
def create(upload_area_uuid: str):
    upload_area = UploadArea(upload_area_uuid)
    upload_area.update_or_create()
    return {'uri': upload_area.uri}, requests.codes.created


@return_exceptions_as_http_errors
def head_upload_area(upload_area_uuid: str):
    _load_upload_area(upload_area_uuid)
    return None, requests.codes.ok


@return_exceptions_as_http_errors
def credentials(upload_area_uuid: str):
    upload_area = _load_upload_area(upload_area_uuid)
    return upload_area.credentials(), requests.codes.created


@return_exceptions_as_http_errors
@require_authenticated
def delete(upload_area_uuid: str):
    upload_area = _load_upload_area(upload_area_uuid)
    upload_area.add_upload_area_to_delete_sqs()
    return None, requests.codes.accepted


@return_exceptions_as_http_errors
@require_authenticated
def lock(upload_area_uuid: str):
    upload_area = _load_upload_area(upload_area_uuid)
    upload_area.lock()
    return None, requests.codes.no_content


@return_exceptions_as_http_errors
@require_authenticated
def unlock(upload_area_uuid: str):
    upload_area = _load_upload_area(upload_area_uuid)
    upload_area.unlock()
    return None, requests.codes.no_content


@return_exceptions_as_http_errors
@require_authenticated
def put_file(upload_area_uuid: str, filename: str, body: str):
    upload_area = _load_upload_area(upload_area_uuid)
    content_type = connexion.request.headers['Content-Type']
    fileinfo = upload_area.store_file(filename, content=body, content_type=content_type)
    return fileinfo, requests.codes.created


@return_exceptions_as_http_errors
def post_file(upload_area_uuid: str, filename: str):
    upload_area = _load_upload_area(upload_area_uuid)
    upload_area.add_uploaded_file_to_csum_daemon_sqs(filename)
    return None, requests.codes.accepted


@return_exceptions_as_http_errors
@require_authenticated
def schedule_file_validation(upload_area_uuid: str, filename: str, json_request_body: str):
    upload_area = _load_upload_area(upload_area_uuid)
    file = upload_area.uploaded_file(urllib.parse.unquote(filename))
    body = json.loads(json_request_body)
    environment = body['environment'] if 'environment' in body else {}
    orig_val_id = body.get('original_validation_id')
    validation_scheduler = ValidationScheduler(file)
    if not validation_scheduler.check_file_can_be_validated():
        raise UploadException(status=requests.codes.bad_request, title="File too large for validation")
    validation_id = validation_scheduler.schedule_validation(body['validator_image'], environment, orig_val_id)
    return {'validation_id': validation_id}, requests.codes.ok


@return_exceptions_as_http_errors
def retrieve_validation_status_and_results(upload_area_uuid: str, filename: str):
    upload_area = _load_upload_area(upload_area_uuid)
    file = upload_area.uploaded_file(urllib.parse.unquote(filename))
    status, results = file.retrieve_latest_file_validation_status_and_results()
    return {'validation_status': status, 'validation_results': results}, requests.codes.ok


@return_exceptions_as_http_errors
def retrieve_checksum_status_and_values(upload_area_uuid: str, filename: str):
    upload_area = _load_upload_area(upload_area_uuid)
    file = upload_area.uploaded_file(urllib.parse.unquote(filename))
    status, checksums = file.retrieve_latest_file_checksum_status_and_values()
    return {'checksum_status': status, 'checksums': checksums}, requests.codes.ok


@return_exceptions_as_http_errors
def retrieve_validation_status_count(upload_area_uuid: str):
    upload_area = _load_upload_area(upload_area_uuid)
    status_count = upload_area.retrieve_file_validation_statuses_for_upload_area()

    return status_count, requests.codes.ok


@return_exceptions_as_http_errors
def retrieve_checksum_status_count(upload_area_uuid: str):
    upload_area = _load_upload_area(upload_area_uuid)
    status_count = upload_area.retrieve_file_checksum_statuses_for_upload_area()
    return status_count, requests.codes.ok


@return_exceptions_as_http_errors
def update_checksum_event(upload_area_uuid: str, checksum_id: str, body: str):
    _load_upload_area(upload_area_uuid)
    body = json.loads(body)
    status = body["status"]
    job_id = body["job_id"]
    payload = body["payload"]
    file_name = payload["name"]
    file_key = f"{upload_area_uuid}/{file_name}"

    checksum_event = UploadedFileChecksumEvent(file_id=file_key, checksum_id=checksum_id, job_id=job_id, status=status)
    if checksum_event.status == "CHECKSUMMED":
        checksum_event.checksums = payload["checksums"]
        _notify_ingest(payload, "file_uploaded")
    checksum_event.update_record()

    return None, requests.codes.no_content


@return_exceptions_as_http_errors
def update_validation_event(upload_area_uuid: str, validation_id: str, body: str):
    _load_upload_area(upload_area_uuid)
    body = json.loads(body)
    status = body["status"]
    job_id = body["job_id"]
    payload = body["payload"]
    file_name = payload["name"]
    file_key = f"{upload_area_uuid}/{file_name}"

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
def list_files(upload_area_uuid: str):
    upload_area = _load_upload_area(upload_area_uuid)
    return upload_area.ls(), requests.codes.ok


@return_exceptions_as_http_errors
def file_info(upload_area_uuid: str, filename: str):
    upload_area = _load_upload_area(upload_area_uuid)
    uploaded_file = upload_area.uploaded_file(filename)
    return uploaded_file.info(), requests.codes.ok


@return_exceptions_as_http_errors
def files_info(upload_area_uuid: str, body: str):
    filename_list = json.loads(body)
    upload_area = _load_upload_area(upload_area_uuid)
    response_data = []
    for filename in filename_list:
        uploaded_file = upload_area.uploaded_file(filename)
        response_data.append(uploaded_file.info())
    return response_data, requests.codes.ok


def _load_upload_area(upload_area_uuid: str):
    upload_area = UploadArea(upload_area_uuid)
    if not upload_area.is_extant():
        raise UploadException(status=requests.codes.not_found, title="Upload Area Not Found")
    return upload_area


def _notify_ingest(payload, notification_type):
    status = IngestNotifier(notification_type).format_and_send_notification(payload)
    logger.info(f"Notified Ingest: payload={payload}, status={status}")
