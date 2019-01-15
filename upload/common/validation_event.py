import os
from datetime import datetime

from .logging import get_logger
if not os.environ.get("CONTAINER"):
    from .database import UploadDB

logger = get_logger(__name__)


class UploadedFileValidationEvent:

    def __init__(self, **kwargs):
        self.id = kwargs["validation_id"]
        self.job_id = kwargs["job_id"]
        self.file_id = kwargs["file_id"]
        self.status = kwargs["status"]
        self.results = None
        self.docker_image = kwargs.get("docker_image")
        self.original_validation_id = kwargs.get("original_validation_id")
        if not os.environ.get("CONTAINER"):
            self.db = UploadDB()

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

        if self.docker_image:
            vals_dict["docker_image"] = self.docker_image
        if self.original_validation_id:
            vals_dict["original_validation_id"] = self.original_validation_id

        return vals_dict

    def create_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        self.db.create_pg_record("validation", prop_vals_dict)

    def update_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        self.db.update_pg_record("validation", prop_vals_dict)
