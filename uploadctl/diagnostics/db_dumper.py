from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from upload.common.upload_config import UploadConfig
from upload.common.database_orm import Base, DbUploadArea


class DbDumper:

    def __init__(self):
        engine = create_engine(UploadConfig().database_uri)
        Base.metadata.bind = engine
        db_session_maker = sessionmaker()
        db_session_maker.bind = engine
        self.db = db_session_maker()

    def dump_all(self):
        for area in self.db.query(DbUploadArea).all():
            self.print_area(area)

    def dump_one_area(self, upload_area_id):
        area = self.db.query(DbUploadArea).filter(DbUploadArea.id == upload_area_id).one()
        self.print_area(area)

    def print_area(self, area):
        print(f"\nUPLOAD AREA {area.bucket_name}/{area.id}:\n"
              f"\tStatus {area.status} Created {area.created_at} Updated {area.updated_at}")

        for file in area.files:
            print(f"\t{file.name}")
            for csum in file.checksums:
                print(f"\t\tchecksum: {csum.id} {csum.status} ended_at {csum.checksum_ended_at}")
            for validation in file.validations:
                print(f"\t\tvalidation: {validation.id} {validation.status} ended_at {validation.validation_ended_at}")
