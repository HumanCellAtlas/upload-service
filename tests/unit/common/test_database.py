import uuid

from .. import UploadTestCaseUsingLiveAWS

from upload.common.database import UploadDB
from upload.common.upload_area import UploadArea
from upload.common.upload_config import UploadConfig


class TestDatabase(UploadTestCaseUsingLiveAWS):

    def setUp(self):
        super().setUp()
        # Config
        self.config = UploadConfig()
        self.config.set({
            'bucket_name': "test_bucket_name",
            'csum_upload_q_url': "bogo_url",
            'area_deletion_q_url': "delete_sqs_url",
            'area_deletion_lambda_name': "delete_lambda_name"
        })

        self.area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.area_id)
        self.db = UploadDB()

        self.db.create_pg_record("upload_area", {
            "id": self.area_id,
            "status": "UNLOCKED",
            "bucket_name": self.config.bucket_name
        })

    def test_get_pg_record(self):
        result = self.db.get_pg_record("upload_area", self.area_id)

        self.assertEqual(result["id"], self.area_id)
        self.assertEqual(result["bucket_name"], self.config.bucket_name)
        self.assertEqual(result["status"], "UNLOCKED")

    def test_update_pg_record(self):
        before = self.db.get_pg_record("upload_area", self.area_id)
        self.assertEqual(before["status"], "UNLOCKED")

        self.db.update_pg_record("upload_area", {
            "id": self.area_id,
            "status": "LOCKED",
            "bucket_name": self.config.bucket_name
        })

        after = self.db.get_pg_record("upload_area", self.area_id)
        self.assertEqual(after["id"], self.area_id)
        self.assertEqual(after["bucket_name"], self.config.bucket_name)
        self.assertEqual(after["status"], "LOCKED")
