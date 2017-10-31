from .uploaded_file import UploadedFile
from .upload_area import UploadArea
from .media_type import MediaType


class UploadException(Exception):
    def __init__(self, status: int, title: str, detail: str=None, *args) -> None:
        super().__init__(*args)
        self.status = status
        self.title = title
        self.detail = detail
