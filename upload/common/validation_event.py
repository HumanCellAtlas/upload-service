import os
from datetime import datetime

from .logging import get_logger
if not os.environ.get("CONTAINER"):
    from .database import create_pg_record, update_pg_record

logger = get_logger(__name__)


class UploadedFileValidationEvent:

    def __init__(self, **kwargs):
        self.id = kwargs["validation_id"]
        self.job_id = kwargs["job_id"]
        self.file_id = kwargs["file_id"]
        self.status = kwargs["status"]

    def _format_prop_vals_dict(self):
        vals_dict = {
            "id": self.id,
            "file_id": self.file_id,
            "status": self.status,
            "job_id": self.job_id
        }

        if self.status == "VALIDATING":
            vals_dict["validation_started_at"] = datetime.utcnow()
        elif self.status == "VALIDATED":
            vals_dict["validation_ended_at"] = datetime.utcnow()
            vals_dict["results"] = self.results

        return vals_dict

    def create_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        create_pg_record("validation", prop_vals_dict)

    def update_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        update_pg_record("validation", prop_vals_dict)
