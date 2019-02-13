import json
import logging
import urllib.parse

import connexion
import requests

from .. import return_exceptions_as_http_errors, require_authenticated
from ....common.checksum_event import ChecksumEvent
from ....common.dss_checksums import DssChecksums
from ....common.exceptions import UploadException
from ....common.ingest_notifier import IngestNotifier
from ....common.upload_area import UploadArea
from ....common.uploaded_file import UploadedFile
from ....common.validation_event import ValidationEvent
from ....common.validation_scheduler import ValidationScheduler

logger = logging.getLogger(__name__)


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
    file = upload_area.store_file(filename, content=body, content_type=content_type)
    return file.info(), requests.codes.created


@return_exceptions_as_http_errors
def post_file(upload_area_uuid: str, filename: str):
    upload_area = _load_upload_area(upload_area_uuid)
    upload_area.add_uploaded_file_to_csum_daemon_sqs(filename)
    return None, requests.codes.accepted


@return_exceptions_as_http_errors
@require_authenticated
def schedule_file_validation(upload_area_uuid: str, filename: str, json_request_body: str):
    upload_area = _load_upload_area(upload_area_uuid)
    filename = urllib.parse.unquote(filename)
    file = upload_area.uploaded_file(filename)
    body = json.loads(json_request_body)
    env = body['environment'] if 'environment' in body else {}
    orig_val_id = body.get('original_validation_id')
    image = body['validator_image']
    validation_scheduler = ValidationScheduler(file)
    if not validation_scheduler.check_file_can_be_validated():
        raise UploadException(status=requests.codes.bad_request, title="File too large for validation")
    validation_id = validation_scheduler.add_to_validation_sqs(filename, image, env, orig_val_id)
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
    _load_upload_area(upload_area_uuid)  # security check
    body = json.loads(body)
    payload = body["payload"]

    checksum_event = ChecksumEvent.load(db_id=checksum_id)
    checksum_event.status = body['status']
    checksum_event.job_id = body['job_id']

    if checksum_event.status == "CHECKSUMMED":
        uploaded_file = UploadedFile.from_db_id(checksum_event.file_id)
        uploaded_file.checksums = payload['checksums']

        """
        Do a last minute check to see if the S3 object for this file still has checksum
        tags.  The tags are erased if the file is overwritten, which happens a lot as
        Ingest tends to upload the same file multiple times simultaneously.  If the
        checksums are gone don't notify Ingest.  Some other checksummer kicked off by
        the new upload will take care of that.
        """
        if DssChecksums(s3_object=uploaded_file.s3object).are_present():
            _notify_ingest(checksum_event.file_id, payload, "file_uploaded")
    checksum_event.update_record()

    return None, requests.codes.no_content


@return_exceptions_as_http_errors
def update_validation_event(upload_area_uuid: str, validation_id: str, body: str):
    _load_upload_area(upload_area_uuid)  # security check
    body = json.loads(body)
    status = body["status"]
    job_id = body["job_id"]
    payload = body["payload"]

    validation_event = ValidationEvent.load(db_id=validation_id)
    validation_event.job_id = job_id
    validation_event.status = status

    if validation_event.status == "VALIDATED":
        validation_event.results = payload
        _notify_ingest(validation_event.file_id, payload, "file_validated")
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


def _notify_ingest(file_id, payload, notification_type):
    status = IngestNotifier(notification_type, file_id).format_and_send_notification(payload)
    logger.info(f"Notified Ingest: payload={payload}, status={status}")
