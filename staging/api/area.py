import requests

from . import StagingException, return_exceptions_as_http_errors, require_authenticated
from .staging_area import StagingArea


@return_exceptions_as_http_errors
@require_authenticated
def create(staging_area_id: str):
    staging_area = StagingArea(staging_area_id)
    if staging_area.is_extant():
        raise StagingException(status=requests.codes.conflict, title="Staging Area Already Exists",
                               detail=f"Staging area {staging_area_id} already exists.")
    staging_area.create()
    return {'urn': staging_area.urn()}, requests.codes.created


@return_exceptions_as_http_errors
@require_authenticated
def delete(staging_area_id: str):
    staging_area = _load_staging_area(staging_area_id)
    staging_area.delete()
    return None, requests.codes.no_content


@return_exceptions_as_http_errors
@require_authenticated
def lock(staging_area_id: str):
    staging_area = _load_staging_area(staging_area_id)
    staging_area.lock()
    return None, requests.codes.ok


@return_exceptions_as_http_errors
@require_authenticated
def unlock(staging_area_id: str):
    staging_area = _load_staging_area(staging_area_id)
    staging_area.unlock()
    return None, requests.codes.ok


@return_exceptions_as_http_errors
@require_authenticated
def put_file(staging_area_id: str, filename: str, body: str):
    staging_area = _load_staging_area(staging_area_id)
    fileinfo = staging_area.store_file(filename, content=body)
    return fileinfo, requests.codes.ok


@return_exceptions_as_http_errors
def list_files(staging_area_id: str):
    staging_area = _load_staging_area(staging_area_id)
    return staging_area.ls(), requests.codes.ok


def _load_staging_area(staging_area_id: str):
    staging_area = StagingArea(staging_area_id)

    if not staging_area.is_extant():
        raise StagingException(status=requests.codes.not_found, title="Staging Area Not Found")
    return staging_area
