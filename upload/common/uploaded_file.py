import os

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.sql import and_
from tenacity import retry, stop_after_attempt, wait_fixed

from .dss_checksums import DssChecksums
from .exceptions import UploadException

if not os.environ.get("CONTAINER"):
    from .database import UploadDB

s3 = boto3.resource('s3')
s3_client = boto3.client('s3')


class UploadedFile:
    """
    The UploadedFile class represents newly-uploaded or previously uploaded files.
    """

    @classmethod
    def create(cls, upload_area, checksums={}, name=None, content_type=None, data=None):
        """ Check if the file exists already and if so, return it. """
        obj_key = f"{upload_area.uuid}/{name}"

        found_file = None
        try:
            obj = s3_client.head_object(Bucket=upload_area.bucket_name, Key=obj_key)
            if obj and 'Metadata' in obj:
                if obj['Metadata'] == checksums:
                    found_file = obj
        except ClientError:
            # An exception from calling `head_object` indicates that no file with the specified name could be found
            # in the specified bucket. No further action is needed since the file will be created.
            pass

        if found_file:
            return UploadedFile.from_s3_key(upload_area, obj_key)

        s3_client.put_object(Body=data, ContentType=content_type, Bucket=upload_area.bucket_name, Key=obj_key,
                             Metadata=checksums)
        s3_object = upload_area.s3_object_for_file(name)
        return cls(upload_area, s3object=s3_object, recently_uploaded=True)

    @classmethod
    def from_s3_key(cls, upload_area, s3_key):
        s3object = s3.Bucket(upload_area.bucket_name).Object(s3_key)
        return cls(upload_area, s3object=s3object, recently_uploaded=False)

    @classmethod
    def from_db_id(cls, db_id):
        db = UploadDB()
        file_props = db.get_pg_record('file', record_id=db_id)
        area_props = db.get_pg_record('upload_area', record_id=file_props['upload_area_id'])
        from .upload_area import UploadArea
        upload_area = UploadArea(area_props['uuid'])
        s3object = upload_area.s3_object_for_file(file_props['name'])
        return cls(upload_area, s3object=s3object)

    def __init__(self, upload_area, s3object, recently_uploaded=False):
        """
        The object of init() is to:
        - populate properties from the S3 object
        - create a DB record for this file of one does not exist
        - initialize a DssChecksums object
        """
        self.upload_area = upload_area
        self.s3object = s3object

        # Properties persisted in DB
        self._properties = {
            "id": None,
            "s3_key": None,
            "s3_etag": None,
            "upload_area_id": upload_area.db_id,
            "name": None,
            "size": None,
            "checksums": None
        }

        if recently_uploaded:
            # This is to account for s3 eventual consistency to ensure file gets checksummed.
            # This may lead to api gateway timeouts that should be retried by client.
            self.recently_uploaded = True
            self._s3_load_with_long_retry()
        else:
            self.recently_uploaded = False
            self._s3_load()
        self._populate_properties_from_s3_object()

        self._db = UploadDB()
        e_tag = self.s3object.e_tag.strip('\"')
        if self._db_load(self.s3object.key, e_tag) is None:
            self._db_create()

    def __str__(self):
        return f"UploadedFile(id={self.db_id}, s3_key={self.s3_key}, etag={self.s3_etag})"

    @property
    def db_id(self):
        return self._properties['id']

    @property
    def s3_key(self):
        return self._properties['s3_key']

    @property
    def s3_etag(self):
        return self._properties['s3_etag']

    @property
    def name(self):
        return self._properties['name']

    @property
    def size(self):
        return self._properties['size']

    @property
    def checksums(self):
        return self._properties['checksums']

    @checksums.setter
    def checksums(self, newval):
        self._properties['checksums'] = newval
        self._db_update()

    @property
    def s3url(self):
        return f"s3://{self.upload_area.bucket_name}/{self.s3_key}"

    @property
    def content_type(self):
        return self.s3object.content_type

    @property
    def s3_last_modified(self):
        return self.s3object.last_modified

    def info(self):
        return {
            # we should rename upload_area_id to upload_area_uuid, but let's keep the API the same for now.
            'upload_area_id': self.upload_area.uuid,  # TBD rename key to upload_area_uuid
            'name': self.name,
            'size': self.size,
            'content_type': self.content_type,
            'url': self.s3url,
            'checksums': self.checksums,
            'last_modified': self.s3_last_modified.isoformat()
        }

    def refresh(self):
        self.s3object.reload()

    def retrieve_latest_file_validation_status_and_results(self):
        status = "UNSCHEDULED"
        results = "N/A"
        query_results = self._db.run_query_with_params(
            "SELECT status, results->>'stdout' "
            "FROM validation "
            "INNER JOIN validation_files ON validation.id = validation_files.validation_id  "
            "INNER JOIN file ON validation_files.file_id = file.id "
            "WHERE file.id = %s;", (self.db_id,))
        rows = query_results.fetchall()
        if rows:
            status = rows[0][0]
            results = rows[0][1]
        return status, results

    def retrieve_latest_file_checksum_status_and_values(self):
        status = "UNSCHEDULED"
        query_results = self._db.run_query_with_params("SELECT status FROM checksum \
            WHERE file_id = %s ORDER BY created_at DESC LIMIT 1;", (self.db_id,))
        rows = query_results.fetchall()
        if rows:
            status = rows[0][0]
        return status, self.checksums

    @retry(reraise=True, wait=wait_fixed(2), stop=stop_after_attempt(3))
    def _s3_load(self):
        try:
            self.s3object.load()
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise UploadException(status=404, title="No such file",
                                      detail=f"No such file in that upload area")
            else:
                raise e

    @retry(reraise=True, wait=wait_fixed(2), stop=stop_after_attempt(150))
    def _s3_load_with_long_retry(self):
        try:
            self.s3object.load()
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise UploadException(status=404, title="No such file",
                                      detail=f"No such file in that upload area")
            else:
                raise e

    def _populate_properties_from_s3_object(self):
        checksums = DssChecksums(self.s3object)
        self._properties = {
            **self._properties,
            's3_key': self.s3object.key,
            's3_etag': self.s3object.e_tag.strip('\"'),
            'name': self.s3object.key[self.upload_area.key_prefix_length:],  # cut off upload-area-id/
            'size': self.s3object.content_length,
            'checksums': dict(checksums) if checksums.are_present() else None
        }

    def _db_load(self, s3_key, s3_etag):
        sql_table = self._db.table('file')
        query = sql_table.select().where(and_(sql_table.columns['s3_key'] == s3_key,
                                              sql_table.columns['s3_etag'] == s3_etag))
        result = self._db.run_query(query)
        rows = result.fetchall()
        if not rows:
            return None
        if len(rows) > 1:
            raise UploadException(status=500, title=">1 match for File query",
                                  detail=f"{len(rows)} matched query for {s3_key} {s3_etag}")
        else:
            if self.s3object:
                # Sanity checks:
                assert rows[0][result.keys().index('name')] == os.path.basename(s3_key)  # Yes, !Windows :)
                assert rows[0][result.keys().index('size')] == self.s3object.content_length
            self._properties = {
                **self._properties,
                'id': rows[0][result.keys().index('id')],
                's3_key': s3_key,
                's3_etag': s3_etag,
                'name': rows[0][result.keys().index('name')],
                'size': rows[0][result.keys().index('size')],
                'checksums': rows[0][result.keys().index('checksums')]
            }
            return True

    def _db_serialize(self):
        prop_vals_dict = self._properties.copy()
        if prop_vals_dict['id'] is None:
            del prop_vals_dict['id']
        return prop_vals_dict

    def _db_create(self):
        prop_vals_dict = self._db_serialize()
        self._properties['id'] = self._db.create_pg_record("file", prop_vals_dict)

    def _db_update(self):
        prop_vals_dict = self._db_serialize()
        self._db.update_pg_record("file", prop_vals_dict)
