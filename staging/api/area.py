import requests

from . import StagingException, return_exceptions_as_http_errors
from .staging_area import StagingArea


@return_exceptions_as_http_errors
def create(staging_area_id: str):
    staging_area = StagingArea(staging_area_id)
    if staging_area.is_extant():
        raise StagingException(status=requests.codes.conflict, title="Staging Area Already Exists",
                               detail=f"Staging area {staging_area_id} already exists.")
    staging_area.create()
    return {'urn': staging_area.urn()}, requests.codes.created


@return_exceptions_as_http_errors
def delete(staging_area_id: str):
    staging_area = _load_staging_area(staging_area_id)
    staging_area.delete()
    return None, 204


@return_exceptions_as_http_errors
def lock(staging_area_id: str):
    staging_area = _load_staging_area(staging_area_id)
    staging_area.lock()
    return None, requests.codes.ok


@return_exceptions_as_http_errors
def unlock(staging_area_id: str):
    staging_area = _load_staging_area(staging_area_id)
    staging_area.unlock()
    return None, requests.codes.ok


@return_exceptions_as_http_errors
def put_file(staging_area_id: str, filename: str, body: str):
    staging_area = _load_staging_area(staging_area_id)
    file_staged_url = staging_area.store_file(filename, content=body)
    return {'url': file_staged_url}, requests.codes.ok


@return_exceptions_as_http_errors
def list_files(staging_area_id: str):
    staging_area = _load_staging_area(staging_area_id)
    return staging_area.ls(), requests.codes.ok


def _load_staging_area(staging_area_id: str):
    staging_area = StagingArea(staging_area_id)

    if not staging_area.is_extant():
        raise StagingException(status=requests.codes.not_found, title="Staging Area Not Found")
    return staging_area
