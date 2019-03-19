import requests

from upload.common.database import UploadDB
from upload.lambdas.api_server import return_exceptions_as_http_errors


@return_exceptions_as_http_errors
def health():
    # This query checks the health of underlying db infrastructure (pgbouncer + rds)
    db_health_check_query = "SELECT count(*) from upload_area;"
    UploadDB().run_query(db_health_check_query)
    return requests.codes.ok
