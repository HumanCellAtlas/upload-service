
from . import StagingException, return_exceptions_as_http_errors
from .staging_area import StagingArea, AwsStagingArea


@return_exceptions_as_http_errors
def create(staging_area_id: str):
    staging_area = AwsStagingArea(staging_area_id)
    if staging_area.is_extant():
        raise StagingException(status=409, title="Staging Area Already Exists",
                               detail=f"Staging area {staging_area_id} already exists.")
    staging_area.create()
    return {'urn': staging_area.urn()}, 201


@return_exceptions_as_http_errors
def delete(staging_area_id: str):
    staging_area = AwsStagingArea(staging_area_id)
    if not staging_area.is_extant():
        raise StagingException(status=404, title="Staging Area Not Found")
    staging_area.delete()
    return None, 204
