from datetime import datetime
from .logging import get_logger
from .logging import format_logger_with_id
from .database import create_pg_record, update_pg_record

logger = get_logger(__name__)


class UploadedFileChecksumEvent:

    def __init__(self, **kwargs):
        self.job_id = kwargs.get("job_id")
        self.id = kwargs["checksum_id"]
        self.file_id = kwargs["file_id"]
        self.status = kwargs["status"]

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
            vals_dict["checksums"] = self.checksums

        return vals_dict

    def create_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        create_pg_record("checksum", prop_vals_dict)

    def update_record(self):
        prop_vals_dict = self._format_prop_vals_dict()
        update_pg_record("checksum", prop_vals_dict)
