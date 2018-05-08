from datetime import datetime
import os

from sqlalchemy import create_engine, MetaData

from .upload_config import UploadConfig

config = UploadConfig()
engine = create_engine(config.database_uri)
conn = engine.connect()

meta = MetaData(engine, reflect=True)

record_type_table_map = {
    "upload_area": meta.tables['upload_area'],
    "file": meta.tables['file'],
    "notification": meta.tables['notification'],
    "validation": meta.tables['validation'],
    "checksum": meta.tables['checksum']
}


def create_pg_record(record_type, prop_vals_dict):
    prop_vals_dict["created_at"] = datetime.utcnow()
    prop_vals_dict["updated_at"] = datetime.utcnow()
    table = record_type_table_map[record_type]
    ins = table.insert().values(prop_vals_dict)
    conn.execute(ins)


def update_pg_record(record_type, prop_vals_dict):
    record_id = prop_vals_dict["id"]
    del prop_vals_dict["id"]
    prop_vals_dict["updated_at"] = datetime.utcnow()
    table = record_type_table_map[record_type]
    update = table.update().where(table.c.id == record_id).values(prop_vals_dict)
    conn.execute(update)


def get_pg_record(record_type, record_id):
    table = record_type_table_map[record_type]
    select = table.select().where(table.c.id == record_id)
    result = conn.execute(select)
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
