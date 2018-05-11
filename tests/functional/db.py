from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from upload.common.upload_config import UploadConfig


Base = declarative_base()


class AreaRecord(Base):
    __tablename__ = 'upload_area'
    id = Column(String(64), primary_key=True)
    bucket_name = Column(String(250), nullable=False)
    status = Column(String(250), nullable=False)


class ChecksumRecord(Base):
    __tablename__ = 'checksum'
    id = Column(String(64), primary_key=True)
    file_id = Column(String(250), nullable=False)
    job_id = Column(String(250), nullable=False)
    status = Column(String(250), nullable=False)


class ValidationRecord(Base):
    __tablename__ = 'validation'
    id = Column(String(64), primary_key=True)
    file_id = Column(String(250), nullable=False)
    job_id = Column(String(250), nullable=False)
    status = Column(String(250), nullable=False)
    results = Column(String(1024), nullable=False)


engine = create_engine(UploadConfig().database_uri)
Base.metadata.bind = engine
db_session_maker = sessionmaker()
db_session_maker.bind = engine
# db = db_session_maker()
