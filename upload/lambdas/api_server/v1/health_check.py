import requests

from upload.common.database import UploadDB
from upload.lambdas.api_server import return_exceptions_as_http_errors


@return_exceptions_as_http_errors
def health():
    """
    This api endpoint is invoked by the dcp wide status monitoring system.
    This function checks the health of underlying api gateway and db infrastructure.
    Running a simple query confirms that ecs pgbouncer is up running and talking to rds.
    """
    db_health_check_query = "SELECT count(*) from upload_area;"
    UploadDB().run_query(db_health_check_query)
    return requests.codes.ok
