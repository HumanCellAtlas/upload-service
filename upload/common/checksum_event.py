import logging
import os
from datetime import datetime

if not os.environ.get("CONTAINER"):
    from .database import UploadDB

logger = logging.getLogger(__name__)


class ChecksumEvent:

    @classmethod
    def load(cls, db_id):
        db = UploadDB()
        prop_vals_dict = db.get_pg_record("checksum", db_id)
        return cls(
            checksum_id=db_id,
            job_id=prop_vals_dict['job_id'],
            file_id=prop_vals_dict['file_id'],
            status=prop_vals_dict['status']
        )

    def __init__(self, **kwargs):
        self.job_id = kwargs.get("job_id")
        self.id = kwargs["checksum_id"]
        self.file_id = kwargs.get("file_id")
        self.status = kwargs.get("status")
        if not os.environ.get('CONTAINER'):
            self.db = UploadDB()

    def _format_prop_vals_dict(self):
        vals_dict = {
            "id": self.id,
            "file_id": self.file_id,
            "status": self.status,
            "job_id": self.job_id
        }

        if self.status == "CHECKSUMMING":
            vals_dict["checksum_started_at"] = datetime.utcnow()
        elif self.status == "CHECKSUMMED":
            vals_dict["checksum_ended_at"] = datetime.utcnow()

        return vals_dict

    def create_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        self.db.create_pg_record("checksum", prop_vals_dict)

    def update_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        self.db.update_pg_record("checksum", prop_vals_dict)
