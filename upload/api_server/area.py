import connexion, requests

from . import UploadException, return_exceptions_as_http_errors, require_authenticated
from .. import UploadArea


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
def list_files(upload_area_id: str):
    upload_area = _load_upload_area(upload_area_id)
    return upload_area.ls(), requests.codes.ok


def _load_upload_area(upload_area_id: str):
    upload_area = UploadArea(upload_area_id)

    if not upload_area.is_extant():
        raise UploadException(status=requests.codes.not_found, title="Upload Area Not Found")
    return upload_area
