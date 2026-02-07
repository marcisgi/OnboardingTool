from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, BYTEA

from .db import Base


tool_status_enum = Enum("Active", "Deprecated", "Planned", name="tool_status")


class OnboardingTool(Base):
    __tablename__ = "onboarding_tools"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), unique=True, nullable=False)
    description = Column(Text)
    logo_data = Column(BYTEA)
    logo_content_type = Column(String(100))
    category = Column(String(100), nullable=False)
    tags = Column(JSONB, default=list)
    owner_teams = Column(JSONB, default=list)
    access_owner_name = Column(String(200))
    access_owner_email = Column(String(200))
    access_process = Column(Text)
    experts = Column(JSONB, default=list)
    documentation_links = Column(JSONB, default=list)
    tool_url = Column(String(500))
    status = Column(tool_status_enum, nullable=False, server_default="Active")
    sort_order = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    last_reviewed = Column(Date)
    reviewed_by = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def has_logo(self) -> bool:
        return bool(self.logo_data)


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    description = Column(Text)
    members = Column(JSONB, default=list)


class ToolAccess(Base):
    __tablename__ = "tool_access"

    id = Column(Integer, primary_key=True)
    tool_id = Column(Integer, nullable=False)
    tool_title = Column(String(200), nullable=False)
    action = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_email = Column(String(200))
