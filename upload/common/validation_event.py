import os
from datetime import datetime

from .logging import get_logger
if not os.environ.get("CONTAINER"):
    from .database import UploadDB

logger = get_logger(__name__)


class ValidationEvent:

    @classmethod
    def load(cls, db_id):
        db = UploadDB()
        prop_vals_dict = db.get_pg_record("validation", db_id)
        return cls(
            validation_id=db_id,
            job_id=prop_vals_dict['job_id'],
            file_id=prop_vals_dict['file_id'],
            status=prop_vals_dict['status'],
            docker_image=prop_vals_dict['docker_image']
        )

    def __init__(self, **kwargs):
        self.id = kwargs["validation_id"]
        self.job_id = kwargs.get("job_id")
        self.file_id = kwargs.get("file_id")
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
