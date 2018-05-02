import uuid

from .. import UploadTestCaseUsingLiveAWS

from upload.common.database import create_pg_record, update_pg_record, get_pg_record
from upload.common.upload_area import UploadArea


class TestDatabase(UploadTestCaseUsingLiveAWS):

    def setUp(self):
        super().setUp()
        self.area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.area_id)
        self.bucket_name = "test_bucket_name"

        create_pg_record("upload_area", {
            "id": self.area_id,
            "status": "UNLOCKED",
            "bucket_name": self.bucket_name
        })

    def test_get_pg_record(self):
        result = get_pg_record("upload_area", self.area_id)

        self.assertEqual(result["id"], self.area_id)
        self.assertEqual(result["bucket_name"], self.bucket_name)
        self.assertEqual(result["status"], "UNLOCKED")

    def test_update_pg_record(self):
        before = get_pg_record("upload_area", self.area_id)
        self.assertEqual(before["status"], "UNLOCKED")

        update_pg_record("upload_area", {
            "id": self.area_id,
            "status": "LOCKED",
            "bucket_name": self.bucket_name
        })

        after = get_pg_record("upload_area", self.area_id)
        self.assertEqual(after["id"], self.area_id)
        self.assertEqual(after["bucket_name"], self.bucket_name)
        self.assertEqual(after["status"], "LOCKED")
