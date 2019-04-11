import os
import random
import uuid

from sqlalchemy.orm.exc import NoResultFound

from upload.common.database_orm import DBSessionMaker, DbFile
from upload.common.upload_area import UploadArea
from upload.common.uploaded_file import UploadedFile
from .. import UploadTestCaseUsingMockAWS
from ... import FixtureFile


class TestUploadedFile(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        self.db_session_maker = DBSessionMaker()
        self.db = self.db_session_maker.session()

        self.upload_area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.upload_area_id)
        self.upload_area.update_or_create()

    def create_file_record(self, s3object, checksums=None):
        record = DbFile(s3_key=s3object.key,
                        s3_etag=s3object.e_tag.strip('\"'),
                        name=os.path.basename(s3object.key),
                        upload_area_id=self.upload_area.db_id,
                        size=s3object.content_length,
                        checksums=checksums)
        self.db.add(record)
        self.db.commit()
        return record

    def tearDown(self):
        super().tearDown()
        pass

    def test_create__creates_a_new_s3_object_and_db_record(self):
        filename = f"file-{random.randint(0, 999999999)}"
        content_type = "application/octet-stream; dcp-type=data"
        file_content = "file1_content"

        uf = UploadedFile.create(upload_area=self.upload_area,
                                 name=filename,
                                 content_type=content_type,
                                 data=file_content)

        self.assertIsInstance(uf, UploadedFile)
        # S3 Object
        s3_key = f"{self.upload_area_id}/{filename}"
        s3object = self.upload_bucket.Object(s3_key)
        self.assertEqual(content_type, s3object.content_type)
        self.assertEqual(file_content.encode('utf8'), s3object.get()['Body'].read())
        # DB Record
        record = self.db.query(DbFile).filter(DbFile.s3_key == s3_key,
                                              DbFile.s3_etag == s3object.e_tag.strip('\"')).one()
        self.assertEqual(s3_key, record.s3_key)
        self.assertEqual(filename, record.name)
        self.assertEqual(s3object.e_tag.strip('\"'), record.s3_etag)
        self.assertEqual(len(file_content), record.size)
        self.assertEqual(self.upload_area.db_id, record.upload_area_id)

    def test_init__given_existing_entities__initializes_properties_correctly(self):
        filename = f"file-{random.randint(0, 999999999)}"
        s3object = self.create_s3_object(f"{self.upload_area_id}/{filename}")
        file_record = self.create_file_record(s3object)

        uf = UploadedFile(self.upload_area, s3object=s3object)

        # Links to objects
        self.assertEqual(s3object, uf.s3object)
        self.assertEqual(self.upload_area, uf.upload_area)
        # Persisted properties
        self.assertEqual(file_record.id, uf.db_id)
        self.assertEqual(s3object.key, uf.s3_key)
        self.assertEqual(s3object.e_tag.strip('\"'), uf.s3_etag)
        self.assertEqual(self.upload_area.db_id, uf._properties['upload_area_id'])
        self.assertEqual(file_record.name, uf.name)
        self.assertEqual(s3object.content_length, uf.size)

    def test_init__when_no_db_record_exists__creates_a_db_record(self):
        filename = f"file-{random.randint(0, 999999999)}"
        s3object = self.create_s3_object(f"{self.upload_area_id}/{filename}")

        with self.assertRaises(NoResultFound):
            self.db.query(DbFile).filter(DbFile.s3_key == s3object.key,
                                         DbFile.s3_etag == s3object.e_tag.strip('\"')).one()

        uf = UploadedFile(upload_area=self.upload_area, s3object=s3object)

        record = self.db.query(DbFile).filter(DbFile.s3_key == s3object.key,
                                              DbFile.s3_etag == s3object.e_tag.strip('\"')).one()
        self.assertEqual(record.id, uf.db_id)
        self.assertEqual(s3object.key, record.s3_key)
        self.assertEqual(filename, record.name)
        self.assertEqual(s3object.e_tag.strip('\"'), record.s3_etag)
        self.assertEqual(s3object.content_length, record.size)
        self.assertEqual(self.upload_area.db_id, record.upload_area_id)

    def test_init__doesnt_create_db_record_if_one_already_exists(self):
        filename = f"file-{random.randint(0, 999999999)}"
        s3_key = f"{self.upload_area_id}/{filename}"
        s3object = self.create_s3_object(s3_key)
        self.create_file_record(s3object)
        record_count_before = self.db.query(DbFile).filter(DbFile.s3_key == s3_key).count()

        UploadedFile(upload_area=self.upload_area, s3object=s3object)

        record_count_after = self.db.query(DbFile).filter(DbFile.s3_key == s3_key).count()
        self.assertEqual(record_count_before, record_count_after)

    def test_from_s3_key__initializes_correctly(self):
        filename = f"file-{random.randint(0, 999999999)}"
        s3object = self.create_s3_object(f"{self.upload_area_id}/{filename}")
        file_record = self.create_file_record(s3object)

        uf = UploadedFile.from_s3_key(self.upload_area, s3_key=s3object.key)

        self.assertEqual(self.upload_area, uf.upload_area)
        self.assertEqual(s3object, uf.s3object)
        self.assertEqual(file_record.id, uf.db_id)

    def test_from_db_id__initializes_correctly_and_figures_out_which_upload_area_to_use(self):
        filename = f"file-{random.randint(0, 999999999)}"
        s3object = self.create_s3_object(f"{self.upload_area_id}/{filename}")
        file_record = self.create_file_record(s3object)

        uf = UploadedFile.from_db_id(file_record.id)

        self.assertEqual(self.upload_area.uuid, uf.upload_area.uuid)
        self.assertEqual(self.upload_area.db_id, uf.upload_area.db_id)
        self.assertEqual(s3object, uf.s3object)
        self.assertEqual(file_record.id, uf.db_id)

    def test_refresh__picks_up_changed_content_type(self):
        filename = f"file-{random.randint(0, 999999999)}"
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

    def test_checksums_setter_saves_db_record(self):
        filename = f"file-{random.randint(0, 999999999)}"
        s3object = self.create_s3_object(f"{self.upload_area_id}/{filename}")
        file_record = self.create_file_record(s3object)
        uf = UploadedFile.from_db_id(file_record.id)

        uf.checksums = {'foo': 'bar'}

        self.db.refresh(file_record)
        self.assertEqual({'foo': 'bar'}, file_record.checksums)

    def test_info(self):
        test_file = FixtureFile.factory("foo")
        s3object = self.create_s3_object(f"{self.upload_area_id}/foo", content=test_file.contents)
        file_record = self.create_file_record(s3object, checksums=test_file.checksums)
        uf = UploadedFile(self.upload_area, s3object=s3object)

        self.assertEqual({
            'upload_area_id': self.upload_area.uuid,
            'name': file_record.name,
            'size': s3object.content_length,
            'content_type': s3object.content_type,
            'url': f"s3://{s3object.bucket_name}/{s3object.key}",
            'checksums': test_file.checksums,
            'last_modified': s3object.last_modified.isoformat()
        }, uf.info())
