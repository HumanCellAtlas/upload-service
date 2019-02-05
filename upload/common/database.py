import re
from datetime import datetime

import requests
from sqlalchemy import create_engine, MetaData
from sqlalchemy.exc import OperationalError, IntegrityError, DatabaseError

from .exceptions import UploadException
from .upload_config import UploadDbConfig


class UploadDB:

    _engine = None
    _record_type_table_map = None

    def __init__(self):
        if self.__class__._record_type_table_map is None:
            config = UploadDbConfig()
            self.__class__._engine = create_engine(config.pgbouncer_uri, pool_size=1)
            meta = MetaData(self.engine)
            meta.reflect()
            self.__class__._record_type_table_map = {
                "upload_area": meta.tables['upload_area'],
                "file": meta.tables['file'],
                "notification": meta.tables['notification'],
                "validation": meta.tables['validation'],
                "checksum": meta.tables['checksum'],
                "validation_files": meta.tables['validation_files']
            }

    @property
    def engine(self):
        return self.__class__._engine

    def table(self, table_name):
        """
        :param table_name: name of table
        :return: SQLAlchemy Table object
        """
        return self.__class__._record_type_table_map[table_name]

    def create_pg_record(self, record_type, prop_vals_dict):
        prop_vals_dict["created_at"] = prop_vals_dict["updated_at"] = datetime.utcnow()
        table = self.table(table_name=record_type)
        ins = table.insert().values(prop_vals_dict)
        try:
            result = self.run_query(ins)
            assert len(result.inserted_primary_key) == 1
            return result.inserted_primary_key[0]
        except IntegrityError as e:
            if re.search("duplicate key value violates unique constraint", e.orig.pgerror):
                raise UploadException(status=requests.codes.conflict,
                                      title=f"{record_type} Already Exists",
                                      detail=f"{record_type} {prop_vals_dict['id']} already exists")
            else:
                raise e

    def update_pg_record(self, record_type, prop_vals_dict, column='id'):
        record_id = prop_vals_dict[column]
        del prop_vals_dict[column]
        prop_vals_dict["updated_at"] = datetime.utcnow()
        table = self.table(table_name=record_type)
        update = table.update().where(table.columns[column] == record_id).values(prop_vals_dict)
        self.run_query(update)

    def get_pg_record(self, record_type, record_id, column='id'):
        result = self._run_select_query(record_type, record_id, column)
        column_keys = result.keys()
        rows = result.fetchall()
        if len(rows) == 0:
            return None
        elif len(rows) > 1:
            raise RuntimeError(f"There is more than 1 {record_type} with ID {record_id}!")
        else:
            output = {}
            for idx, val in enumerate(rows[0]):
                column = column_keys[idx]
                output[column] = val
            return output

    def get_pg_records(self, record_type, record_id, column):
        result = self._run_select_query(record_type, record_id, column)
        column_keys = result.keys()
        rows = result.fetchall()
        if len(rows) == 0:
            return None
        else:
            results = []
            for row in rows:
                output = {}
                for idx, val in enumerate(row):
                    column = column_keys[idx]
                    output[column] = val
                results.append(output)
        return results

    def _run_select_query(self, record_type, record_id, column):
        table = self.table(table_name=record_type)
        select = table.select().where(table.columns[column] == record_id)
        result = self.run_query(select)
        return result

    # Engine.dispose() protects us from situations where the client thinks it has
    # an active connection but for some reason it is inactive. Potential causes
    # include network issues or pgbouncer dropping inactive client connections after
    # a long idle timeout. Sometimes its difficult to determine how long AWS actually
    # keeps old lambda containers warmed up and waiting. This code path should not be
    # followed often, but it is a good protective measure.

    def run_query(self, query):
        try:
            results = self.engine.execute(query)
        except (OperationalError, DatabaseError) as e:
            self.engine.dispose()
            results = self.engine.execute(query)
        return results

    def run_query_with_params(self, query, params):
        try:
            results = self.engine.execute(query, params)
        except (OperationalError, DatabaseError) as e:
            self.engine.dispose()
            results = self.engine.execute(query, params)
        return results
