import uuid

import boto3
from sqlalchemy.orm.exc import NoResultFound

from .. import UploadTestCaseUsingMockAWS

from upload.common.database_orm import DBSessionMaker, DbFile
from upload.common.upload_area import UploadArea
from upload.common.uploaded_file import UploadedFile


class TestUploadedFile(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        self.db_session_maker = DBSessionMaker()
        self.upload_area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.upload_area_id)
        self.upload_area.update_or_create()

    def tearDown(self):
        super().tearDown()
        pass

    def test_from_s3_key__loads_data_and_creates_db_record_if_none_exists(self):
        db = self.db_session_maker.session()
        filename = "file1"
        file_content = "file1_body"
        s3object = self.create_s3_object(object_key=f"{self.upload_area.uuid}/{filename}",
                                         content=file_content)
        s3_key = s3object.key

        with self.assertRaises(NoResultFound):
            db.query(DbFile).filter(DbFile.id == s3_key).one()

        uf = UploadedFile.from_s3_key(upload_area=self.upload_area, s3_key=s3_key)

        self.assertEqual(filename, uf.name)
        self.assertEqual(self.upload_area, uf.upload_area)
        self.assertEqual(s3object, uf.s3obj)

        record = db.query(DbFile).filter(DbFile.id == s3_key).one()
        self.assertEqual(s3_key, record.id)
        self.assertEqual(filename, record.name)
        self.assertEqual(s3object.e_tag.strip('\"'), record.s3_etag)
        self.assertEqual(len(file_content), record.size)
        self.assertEqual(self.upload_area.db_id, record.upload_area_id)

    def test_from_s3_key__loads_data_but_doesnt_creates_db_record_if_one_exists(self):
        db = self.db_session_maker.session()
        filename = "file2"
        file_content = "file2_body"
        s3object = self.create_s3_object(object_key=f"{self.upload_area.uuid}/{filename}",
                                         content=file_content)
        record = DbFile(id=s3object.key, s3_etag=s3object.e_tag.strip('\"'),
                        name=filename, upload_area_id=self.upload_area.db_id,
                        size=len(file_content))
        db.add(record)
        db.commit()
        record_count_before = db.query(DbFile).count()

        UploadedFile.from_s3_key(s3_key=s3object.key, upload_area=self.upload_area)

        self.assertEqual(record_count_before, db.query(DbFile).count())

    def test_with_data_in_paramaters_it_creates_a_new_file(self):

        UploadedFile(upload_area=self.upload_area, name="file2",
                     content_type="application/octet-stream; dcp-type=data", data="file2_content")

        self.assertEqual("file2_content".encode('utf8'),
                         self.upload_bucket.Object(f"{self.upload_area_id}/file2").get()['Body'].read())

    def test_refresh__picks_up_changed_content_type(self):
        filename = "file3"
        old_content_type = "application/octet-stream"  # missing dcp-type
        new_content_type = "application/octet-stream; dcp-type=data"
        s3object = self.create_s3_object(object_key=f"{self.upload_area.uuid}/{filename}",
                                         content_type=old_content_type)
        # create UploadedFile
        uf = UploadedFile.from_s3_key(upload_area=self.upload_area, s3_key=s3object.key)
        # Change media type on S3 object
        s3object.copy_from(CopySource={'Bucket': self.upload_config.bucket_name, 'Key': s3object.key},
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
