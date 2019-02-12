from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from upload.common.upload_config import UploadDbConfig


Base = declarative_base()


class DbUploadArea(Base):
    __tablename__ = 'upload_area'
    id = Column(Integer(), primary_key=True)
    uuid = Column(String(), nullable=False)
    bucket_name = Column(String(), nullable=False)
    status = Column(String(), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)


class DbFile(Base):
    __tablename__ = 'file'
    id = Column(Integer(), primary_key=True)
    s3_key = Column(String(), nullable=False)
    s3_etag = Column(String(), nullable=True)
    upload_area_id = Column(Integer(), ForeignKey('upload_area.id'), nullable=False)
    name = Column(String(), nullable=False)
    size = Column(Integer(), nullable=False)
    checksums = Column(JSON(), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)

    upload_area = relationship("DbUploadArea", back_populates="files")


class DbChecksum(Base):
    __tablename__ = 'checksum'
    id = Column(String(), primary_key=True)
    file_id = Column(String(), ForeignKey('file.id'), nullable=False)
    job_id = Column(String(), nullable=False)
    status = Column(String(), nullable=False)
    checksum_started_at = Column(DateTime(), nullable=False)
    checksum_ended_at = Column(DateTime(), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)

    file = relationship("DbFile", back_populates='checksum_records')


class DbValidation(Base):
    __tablename__ = 'validation'
    id = Column(String(), primary_key=True)
    file_id = Column(String(), ForeignKey('file.id'), nullable=False)
    job_id = Column(String(), nullable=False)
    status = Column(String(), nullable=False)
    results = Column(String(), nullable=False)
    validation_started_at = Column(DateTime(), nullable=False)
    validation_ended_at = Column(DateTime(), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)

    file = relationship("DbFile", back_populates='validations')


class DbNotification(Base):
    __tablename__ = 'notification'
    id = Column(String(), primary_key=True)
    file_id = Column(String(), ForeignKey('file.id'), nullable=False)
    status = Column(String(), nullable=False)
    payload = Column(JSON(), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)

    file = relationship("DbFile", back_populates='notifications')


DbUploadArea.files = relationship('DbFile', order_by=DbFile.id, back_populates='upload_area')
DbFile.checksum_records = relationship('DbChecksum', order_by=DbChecksum.created_at,
                                       back_populates='file',
                                       cascade='all, delete, delete-orphan')
DbFile.validations = relationship('DbValidation',
                                  order_by=DbValidation.created_at,
                                  back_populates='file',
                                  cascade='all, delete, delete-orphan')
DbFile.notifications = relationship('DbNotification',
                                    order_by=DbNotification.created_at,
                                    back_populates='file',
                                    cascade='all, delete, delete-orphan')


class DBSessionMaker:

    def __init__(self):
        engine = create_engine(UploadDbConfig().database_uri)
        Base.metadata.bind = engine
        self.session_maker = sessionmaker()
        self.session_maker.bind = engine

    def session(self, **kwargs):
        return self.session_maker(**kwargs)
