from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from upload.common.upload_config import UploadConfig


Base = declarative_base()


class DbUploadArea(Base):
    __tablename__ = 'upload_area'
    id = Column(String(), primary_key=True)
    bucket_name = Column(String(), nullable=False)
    status = Column(String(), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)


class DbFile(Base):
    __tablename__ = 'file'
    id = Column(String(), primary_key=True)
    upload_area_id = Column(String(), ForeignKey('upload_area.id'), nullable=False)
    name = Column(String(), nullable=False)
    size = Column(Integer(), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)

    upload_area = relationship("DbUploadArea", back_populates="files")


class DbChecksum(Base):
    __tablename__ = 'checksum'
    id = Column(String(), primary_key=True)
    file_id = Column(String(), ForeignKey('file.id'), nullable=False)
    job_id = Column(String(), nullable=False)
    status = Column(String(), nullable=False)
    checksums = Column(String(), nullable=False)
    checksum_started_at = Column(DateTime(), nullable=False)
    checksum_ended_at = Column(DateTime(), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)

    file = relationship("DbFile", back_populates='checksums')


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


DbUploadArea.files = relationship('DbFile', order_by=DbFile.id, back_populates='upload_area')
DbFile.checksums = relationship('DbChecksum', order_by=DbChecksum.created_at, back_populates='file')
DbFile.validations = relationship('DbValidation', order_by=DbValidation.created_at, back_populates='file')

engine = create_engine(UploadConfig().database_uri)
Base.metadata.bind = engine
db_session_maker = sessionmaker()
db_session_maker.bind = engine
