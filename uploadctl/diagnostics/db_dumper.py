from upload.common.database_orm import db_session_maker, DbUploadArea, DbFile


class DbDumper:

    def __init__(self):
        self.db = db_session_maker()

    def dump_all(self):
        for area in self.db.query(DbUploadArea).all():
            self.print_area(area)

    def dump_one_area(self, upload_area_id, filename):
        area = self.db.query(DbUploadArea).filter(DbUploadArea.id == upload_area_id).one()
        self.print_area(area)
        if filename:
            file = self.db.query(DbFile).filter(DbFile.upload_area_id == upload_area_id, DbFile.name == filename).one()
            self.print_file(file)
        else:
            for file in area.files:
                self.print_file(file)

    def print_area(self, area):
        print(f"\nUPLOAD AREA {area.bucket_name}/{area.id}:\n"
              f"\tStatus {area.status} Created {area.created_at} Updated {area.updated_at}")

    def print_file(self, file):
        print(f"\t{file.name}")
        for csum in file.checksums:
            print(f"\t\tchecksum: {csum.id} {csum.status}")
            print(f"\t\t          job_id {csum.job_id}")
            print(f"\t\t          started_at {csum.checksum_ended_at} ended_at {csum.checksum_ended_at}")
        for validation in file.validations:
            print(f"\t\tvalidation: {validation.id} {validation.status} ended_at {validation.validation_ended_at}")
