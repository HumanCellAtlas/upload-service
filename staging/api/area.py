
from . import StagingException, return_exceptions_as_http_errors
from .staging_area import StagingArea


@return_exceptions_as_http_errors
def create(staging_area_id: str, cloud: str):
    staging_area = StagingArea.factory(staging_area_id, cloud)
    if staging_area.is_extant():
        raise StagingException(status=409, title="Staging Area Already Exists",
                               detail=f"Staging area {staging_area_id} already exists.")
    staging_area.create()
    return {'urn': staging_area.urn()}, 201


@return_exceptions_as_http_errors
def delete(staging_area_id: str, cloud: str):
    staging_area = _load_staging_area(staging_area_id, cloud)
    staging_area.delete()
    return None, 204


@return_exceptions_as_http_errors
def lock(staging_area_id: str, cloud: str):
    staging_area = _load_staging_area(staging_area_id, cloud)
    staging_area.lock()
    return None, 200


@return_exceptions_as_http_errors
def unlock(staging_area_id: str, cloud: str):
    staging_area = _load_staging_area(staging_area_id, cloud)
    staging_area.unlock()
    return None, 200


@return_exceptions_as_http_errors
def put_file(staging_area_id: str, filename: str, cloud: str, body: str):
    staging_area = _load_staging_area(staging_area_id, cloud)
    staging_area.store_file(filename, content=body)
    return None, 200


def _load_staging_area(staging_area_id: str, cloud: str):
    staging_area = StagingArea.factory(staging_area_id, cloud)

    if not staging_area.is_extant():
        raise StagingException(status=404, title="Staging Area Not Found")
    return staging_area
