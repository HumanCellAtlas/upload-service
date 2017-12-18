from .uploaded_file import UploadedFile
from .upload_area import UploadArea
from .validation import Validation
from .event_notifier import EventNotifier


class UploadException(Exception):
    def __init__(self, status: int, title: str, detail: str=None, *args) -> None:
        super().__init__(*args)
        self.status = status
        self.title = title
        self.detail = detail
