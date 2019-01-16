import uuid
from unittest.mock import patch

from botocore.exceptions import ClientError
from moto import mock_sts
from sqlalchemy.orm.exc import NoResultFound

from .. import UploadTestCaseUsingMockAWS

from upload.common.database_orm import DBSessionMaker, DbUploadArea, DbFile
from upload.common.upload_area import UploadArea
from upload.common.uploaded_file import UploadedFile
from upload.common.exceptions import UploadException


class UploadAreaTest(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        self.db_session_maker = DBSessionMaker()
        self.db = self.db_session_maker.session()

    def _create_area(self, status='UNLOCKED'):
        area_uuid = str(uuid.uuid4())
        db_area = DbUploadArea(uuid=area_uuid, bucket_name=self.upload_config.bucket_name, status=status)
        self.db.add(db_area)
        self.db.commit()
        return db_area


class TestUploadAreaCreationExistenceAndDeletion(UploadAreaTest):

    def test_update_or_create__when_no_area_exists__creates_db_record(self):
        area_uuid = str(uuid.uuid4())
        with self.assertRaises(NoResultFound):
            self.db.query(DbUploadArea).filter(DbUploadArea.uuid == area_uuid).one()

        UploadArea(uuid=area_uuid).update_or_create()

        record = self.db.query(DbUploadArea).filter(DbUploadArea.uuid == area_uuid).one()
        self.assertEqual(area_uuid, record.uuid)
        self.assertEqual(self.upload_config.bucket_name, record.bucket_name)
        self.assertEqual("UNLOCKED", record.status)

    def test_update_or_create__when_area_exists__retrieves_db_record(self):
        db_area = self._create_area()

        area = UploadArea(uuid=db_area.uuid)
        area.update_or_create()

        self.assertEqual(db_area.id, area.db_id)

    def test_is_extant__for_nonexistant_area__returns_false(self):
        area_uuid = "an-area-that-will-not-exist"

        self.assertFalse(UploadArea(area_uuid).is_extant())

    def test_is_extant__for_deleted_area__returns_false(self):
        db_area = self._create_area('DELETED')

        self.assertFalse(UploadArea(db_area.uuid).is_extant())

    def test_is_extant__for_existing_area__returns_true(self):
        db_area = self._create_area()

        self.assertTrue(UploadArea(db_area.uuid).is_extant())
        pass

    def test_delete__marks_area_delete_and_deletes_objects(self):
        db_area = self._create_area()
        obj = self.upload_bucket.Object(f'{db_area.uuid}/test_file')
        obj.put(Body="foo")

        with patch('upload.common.upload_area.UploadArea._retrieve_upload_area_deletion_lambda_timeout') as mock_retr:
            mock_retr.return_value = 900

            area = UploadArea(uuid=db_area.uuid)
            area.delete()

        self.db.refresh(db_area)
        self.assertEqual("DELETED", db_area.status)
        with self.assertRaises(ClientError):
            obj.load()


class TestUploadAreaCredentials(UploadAreaTest):

    @mock_sts
    def test_with_deleted_upload_area__raises(self):
        db_area = self._create_area('DELETED')

        with self.assertRaises(UploadException):
            area = UploadArea(db_area.uuid)
            area.credentials()

    @mock_sts
    def test_with_existing_locked_upload_area__raises(self):
        db_area = self._create_area()
        area = UploadArea(db_area.uuid)
        area.lock()

        with self.assertRaises(UploadException):
            area.credentials()

    @mock_sts
    def test_with_existing_unlocked_upload_area__returns_creds(self):
        db_area = self._create_area()

        area = UploadArea(db_area.uuid)
        creds = area.credentials()

        keys = list(creds.keys())
        keys.sort()
        self.assertEqual(['AccessKeyId', 'Expiration', 'SecretAccessKey', 'SessionToken'], keys)


class TestUploadAreaLocking(UploadAreaTest):

    def setUp(self):
        super().setUp()
        self.db_area = self._create_area()
        self.area = UploadArea(uuid=self.db_area.uuid)

    def test_lock__with_unlocked_area__locks_area(self):
        self.assertEqual("UNLOCKED", self.db_area.status)

        self.area.lock()

        self.db.refresh(self.db_area)
        self.assertEqual("LOCKED", self.db_area.status)

    def test_unlock__with_locked_area__unlocks_area(self):
        self.db_area.status = 'LOCKED'
        self.db.add(self.db_area)
        self.db.commit()

        self.area.unlock()

        self.db.refresh(self.db_area)
        self.assertEqual("UNLOCKED", self.db_area.status)


class TestUploadAreaFileManipulation(UploadAreaTest):

    def test_store_file(self):
        db_area = self._create_area()
        area = UploadArea(uuid=db_area.uuid)

        filename = "some.json"
        content_type = 'application/json; dcp-type="metadata/sample"'
        content = "exquisite corpse"
        file = area.store_file(filename, content=content, content_type=content_type)

        s3_key = f"{db_area.uuid}/some.json"
        s3_etag = "18f17fbfdd21cf869d664731e10d4ffd"
        o1 = self.upload_bucket.Object(s3_key)
        o1.load()
        self.assertEqual({
            'upload_area_id': db_area.uuid,
            'name': 'some.json',
            'size': 16,
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/sample"',
            'url': f"s3://{self.upload_config.bucket_name}/{db_area.uuid}/some.json",
            'checksums': {
                "crc32c": "FE9ADA52",
                "s3_etag": s3_etag,
                "sha1": "b1b101e21cf9cf8a4729da44d7818f935eec0ce8",
                "sha256": "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70"
            }
        }, file.info())
        obj = self.upload_bucket.Object(f"{db_area.uuid}/some.json")
        self.assertEqual("exquisite corpse".encode('utf8'), obj.get()['Body'].read())

        db_file = self.db.query(DbFile).filter(DbFile.s3_key == s3_key, DbFile.s3_etag == s3_etag).one()
        self.assertEqual(16, db_file.size)
        self.assertEqual(db_area.id, db_file.upload_area_id)
        self.assertEqual("some.json", db_file.name)

    def test_ls__returns_info_on_all_files_in_upload_area(self):
        db_area = self._create_area()
        o1 = self.mock_upload_file_to_s3(db_area.uuid, 'file1.json',
                                         content_type='application/json; dcp-type="metadata/foo"')
        o2 = self.mock_upload_file_to_s3(db_area.uuid, 'file2.fastq.gz',
                                         content_type='application/octet-stream; dcp-type=data',
                                         checksums={'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'})

        area = UploadArea(uuid=db_area.uuid)
        data = area.ls()

        self.assertIn('size', data['files'][0].keys())  # moto file sizes are not accurate
        for fileinfo in data['files']:
            del fileinfo['size']
        self.assertEqual({
            'upload_area_id': db_area.uuid,
            'name': 'file1.json',
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/foo"',
            'url': f"s3://{self.upload_config.bucket_name}/{db_area.uuid}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        }, data['files'][0])
        self.assertEqual({
            'upload_area_id': db_area.uuid,
            'name': 'file2.fastq.gz',
            'last_modified': o2.last_modified.isoformat(),
            'content_type': 'application/octet-stream; dcp-type=data',
            'url': f"s3://{self.upload_config.bucket_name}/{db_area.uuid}/file2.fastq.gz",
            'checksums': {'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'}
        }, data['files'][1])

    def test_ls__only_lists_files_in_this_upload_area(self):
        db_area1 = self._create_area()
        db_area2 = self._create_area()
        area_1_files = ['file1', 'file2']
        area_2_files = ['file3', 'file4']
        [self.mock_upload_file_to_s3(db_area1.uuid, file) for file in area_1_files]
        [self.mock_upload_file_to_s3(db_area2.uuid, file) for file in area_2_files]

        data = UploadArea(uuid=db_area2.uuid).ls()

        self.assertEqual(area_2_files, [file['name'] for file in data['files']])

    def test_uploaded_file(self):
        db_area = self._create_area()
        filename = "somefile.json"
        content = "sdfewrwer"
        self.mock_upload_file_to_s3(db_area.uuid, filename=filename, contents=content)

        file = UploadArea(uuid=db_area.uuid).uploaded_file(filename)

        self.assertIs(UploadedFile, file.__class__)
        self.assertEqual(filename, file.name)
