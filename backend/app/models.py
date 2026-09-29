from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from .db import Base


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="analyst")
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    name = Column(String, nullable=False)
    original_filename = Column(String)
    source_type = Column(String, default="file")
    n_rows = Column(Integer, default=0)
    n_cols = Column(Integer, default=0)
    current_version = Column(Integer, default=1)
    quality_score = Column(Float, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id = Column(String, primary_key=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), index=True)
    version = Column(Integer, default=1)
    path = Column(String, nullable=False)
    note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Transformation(Base):
    __tablename__ = "transformations"
    id = Column(String, primary_key=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), index=True)
    version_from = Column(Integer)
    version_to = Column(Integer)
    operation = Column(String)
    params_json = Column(Text, default="{}")
    reversible = Column(Boolean, default=True)
    applied = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(String, primary_key=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    research_question = Column(Text, default="")
    method = Column(String)
    params_json = Column(Text, default="{}")
    result_json = Column(Text, default="{}")
    provenance_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    title = Column(String)
    style = Column(String, default="academic")
    path = Column(String)
    format = Column(String, default="html")
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True)
    dataset_id = Column(String, nullable=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), index=True)
    role = Column(String)
    content = Column(Text)
    citations_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True)
    action = Column(String)
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
