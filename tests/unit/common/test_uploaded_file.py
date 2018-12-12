import uuid

import boto3

from .. import UploadTestCaseUsingMockAWS

from upload.common.upload_area import UploadArea
from upload.common.uploaded_file import UploadedFile


class TestUploadedFile(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()

        self.upload_area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.upload_area_id)
        self.upload_area.update_or_create()

    def tearDown(self):
        super().tearDown()
        pass

    def test_from_s3_key(self):
        s3 = boto3.resource('s3')
        filename = "file1"
        content_type = "application/octet-stream; dcp-type=data"
        s3_key = f"{self.upload_area_id}/{filename}"
        s3object = s3.Bucket(self.upload_config.bucket_name).Object(s3_key)
        s3object.put(Body="file1_body", ContentType=content_type)

        uf = UploadedFile.from_s3_key(upload_area=self.upload_area, s3_key=s3_key)
        self.assertEqual(filename, uf.name)

    def test_with_data_in_paramaters_it_creates_a_new_file(self):
        UploadedFile(upload_area=self.upload_area, name="file2",
                     content_type="application/octet-stream; dcp-type=data", data="file2_content")
        self.assertEqual("file2_content".encode('utf8'),
                         self.upload_bucket.Object(f"{self.upload_area_id}/file2").get()['Body'].read())

    def test_refresh_picks_up_changed_content_type(self):
        s3 = boto3.resource('s3')
        filename = "file3"
        # create S3 object
        old_content_type = "application/octet-stream"  # missing dcp-type
        s3_key = f"{self.upload_area_id}/{filename}"
        s3object = s3.Bucket(self.upload_config.bucket_name).Object(s3_key)
        s3object.put(Body="file1_body", ContentType=old_content_type)
        # create UploadedFile
        uf = UploadedFile.from_s3_key(upload_area=self.upload_area, s3_key=s3_key)
        # Change media type on S3 object
        new_content_type = "application/octet-stream; dcp-type=data"
        s3object.copy_from(CopySource={'Bucket': self.upload_config.bucket_name, 'Key': s3_key},
                           MetadataDirective="REPLACE",
                           ContentType=new_content_type)

        self.assertEqual(old_content_type, uf.content_type)

        uf.refresh()

        self.assertEqual(new_content_type, uf.content_type)

    def test_info(self):
        # TODO
        pass

    def test_s3url(self):
        # TODO
        pass

    def test_size(self):
        # TODO
        pass

    def test_save_tags(self):
        # TODO
        pass

    def test_create_record(self):
        # TODO
        pass

    def test_fetch_or_create_db_record(self):
        # TODO
        pass
