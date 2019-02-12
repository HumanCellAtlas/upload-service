import os
from datetime import datetime

import logging
if not os.environ.get("CONTAINER"):
    from .database import UploadDB

logger = logging.getLogger(__name__)


class ValidationEvent:

    @classmethod
    def load(cls, db_id):
        db = UploadDB()
        prop_vals_dict = db.get_pg_record("validation", db_id)
        file_ids = cls._get_file_ids_for_validation(db_id)
        return cls(
            validation_id=db_id,
            file_ids=file_ids,
            job_id=prop_vals_dict['job_id'],
            status=prop_vals_dict['status'],
            docker_image=prop_vals_dict['docker_image']
        )

    @classmethod
    def _get_file_ids_for_validation(cls, db_id):
        db = UploadDB()
        records = db.get_pg_records("validation_files", db_id, "validation_id")
        return [record["file_id"] for record in records]

    def __init__(self, **kwargs):
        self.id = kwargs["validation_id"]
        self.job_id = kwargs.get("job_id")
        self.file_ids = kwargs.get("file_ids")
        self.status = kwargs["status"]
        self.results = None
        self.docker_image = kwargs.get("docker_image")
        self.original_validation_id = kwargs.get("original_validation_id")
        if not os.environ.get("CONTAINER"):
            self.db = UploadDB()

    def _format_prop_vals_dict(self):
        vals_dict = {
            "id": self.id,
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
        for file_id in self.file_ids:
            validation_files_props = {'file_id': file_id, 'validation_id': self.id}
            self.db.create_pg_record("validation_files", validation_files_props)

    def update_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        self.db.update_pg_record("validation", prop_vals_dict)
