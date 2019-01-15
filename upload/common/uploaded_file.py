import os

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.sql import and_

from .dss_checksums import DssChecksums
from .exceptions import UploadException
if not os.environ.get("CONTAINER"):
    from .database import UploadDB

s3 = boto3.resource('s3')
s3client = boto3.client('s3')


class UploadedFile:

    """
    The UploadedFile class represents newly-uploaded or previously uploaded files.

    If the parameters to __init__() include 'name', 'data', 'content_type': a new S3 object will be created.
    """

    @classmethod
    def from_s3_key(cls, upload_area, s3_key):
        s3object = s3.Bucket(upload_area.bucket_name).Object(s3_key)
        return cls(upload_area, s3object=s3object)

    def __init__(self, upload_area, name=None, content_type=None, data=None, s3object=None):
        # Properties persisted in DB
        self._properties = {
            "id": None,
            "s3_key": None,
            "s3_etag": None,
            "upload_area_id": upload_area.db_id,
            "name": None,
            "size": None
        }
        self.upload_area = upload_area
        # internals
        self._s3obj = None
        # utility:
        self._db = UploadDB()

        if name and data and content_type:
            self._s3_create(name, data, content_type)
            self._populate_properties_from_s3_object()
            self._db_create()

        elif s3object:
            self._s3obj = s3object
            self._s3_load()
            e_tag = self._s3obj.e_tag.strip('\"')
            if self._db_load(self._s3obj.key, e_tag) is None:
                self._populate_properties_from_s3_object()
                self._db_create()
        else:
            raise RuntimeError("you must provide s3object, or name, content_type and data")

        self.checksums = DssChecksums(s3_object=self._s3obj)

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
    def s3url(self):
        return f"s3://{self.upload_area.bucket_name}/{self.s3_key}"

    @property
    def content_type(self):
        return self._s3obj.content_type

    @property
    def s3_last_modified(self):
        return self._s3obj.last_modified

    def info(self):
        return {
            # we should rename upload_area_id to upload_area_uuid, but let's keep the API the same for now.
            'upload_area_id': self.upload_area.uuid,  # TBD rename key to upload_area_uuid
            'name': self.name,
            'size': self.size,
            'content_type': self.content_type,
            'url': self.s3url,
            'checksums': dict(self.checksums),
            'last_modified': self.s3_last_modified.isoformat()
        }

    def refresh(self):
        self._s3obj.reload()

    def retrieve_latest_file_validation_status_and_results(self):
        status = "UNSCHEDULED"
        results = None
        query_results = self._db.run_query_with_params("SELECT status, results->>'stdout' FROM validation \
            WHERE file_id = %s ORDER BY created_at DESC LIMIT 1;", (self.db_id,))
        rows = query_results.fetchall()
        if len(rows) > 0:
            status = rows[0][0]
            results = rows[0][1]
        return status, results

    def retrieve_latest_file_checksum_status_and_values(self):
        status = "UNSCHEDULED"
        checksums = None
        query_results = self._db.run_query_with_params("SELECT status, checksums FROM checksum \
            WHERE file_id = %s ORDER BY created_at DESC LIMIT 1;", (self.db_id,))
        rows = query_results.fetchall()
        if len(rows) > 0:
            status = rows[0][0]
            checksums = rows[0][1]
        return status, checksums

    def _s3_create(self, name, data, content_type):
        self._s3obj = self.upload_area.s3_object_for_file(name)
        self._s3obj.put(Body=data, ContentType=content_type)

    def _s3_load(self):
        try:
            self._s3obj.load()
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise UploadException(status=404, title="No such file",
                                      detail=f"No such file in that upload area")
            else:
                raise e

    def _populate_properties_from_s3_object(self):
        self._properties = {
            **self._properties,
            's3_key': self._s3obj.key,
            's3_etag': self._s3obj.e_tag.strip('\"'),
            'name': self._s3obj.key[self.upload_area.key_prefix_length:],  # cut off upload-area-id/
            'size': self._s3obj.content_length
        }

    def _db_load(self, s3_key, s3_etag):
        sql_table = self._db.table('file')
        query = sql_table.select().where(and_(sql_table.columns['s3_key'] == s3_key,
                                              sql_table.columns['s3_etag'] == s3_etag))
        result = self._db.run_query(query)
        rows = result.fetchall()
        if len(rows) == 0:
            return None
        elif len(rows) > 1:
            raise UploadException(status=500, title=">1 match for File query",
                                  detail=f"{len(rows)} matched query for {s3_key} {s3_etag}")
        elif len(rows) == 1:
            if self._s3obj:
                # Sanity checks:
                assert rows[0][result.keys().index('name')] == os.path.basename(s3_key)  # Yes, !Windows :)
                assert rows[0][result.keys().index('size')] == self._s3obj.content_length
            self._properties = {
                **self._properties,
                'id': rows[0][result.keys().index('id')],
                's3_key': s3_key,
                's3_etag': s3_etag,
                'name': rows[0][result.keys().index('name')],
                'size': rows[0][result.keys().index('size')]
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
