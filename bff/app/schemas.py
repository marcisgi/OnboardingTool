from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

import bleach
from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator

ALLOWED_TAGS = [
    "p",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "br",
    "a",
    "code",
    "pre",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
]


class Expert(BaseModel):
    name: str
    email: EmailStr
    title: Optional[str] = None
    is_backup: bool = False


class DocumentationLink(BaseModel):
    title: str
    url: HttpUrl
    type: Optional[str] = None


class ToolBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    tags: List[str] = Field(default_factory=list)
    owner_teams: List[int] = Field(default_factory=list)
    access_owner_name: Optional[str] = None
    access_owner_email: Optional[EmailStr] = None
    access_process: Optional[str] = None
    experts: List[Expert] = Field(default_factory=list)
    documentation_links: List[DocumentationLink] = Field(default_factory=list)
    tool_url: Optional[HttpUrl] = None
    status: Literal["Active", "Deprecated", "Planned"] = "Active"
    sort_order: int = 0
    is_featured: bool = False
    last_reviewed: Optional[date] = None
    reviewed_by: Optional[str] = None

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return bleach.clean(value, tags=ALLOWED_TAGS, attributes={"a": ["href", "title"]}, strip=True)

    @field_validator("title", "category")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value is required.")
        return cleaned


class ToolCreate(ToolBase):
    pass


class ToolUpdate(ToolBase):
    pass


class ToolRead(ToolBase):
    id: int
    has_logo: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ToolBulkRequest(BaseModel):
    tools: List[ToolCreate]


class TeamMember(BaseModel):
    name: str
    email: EmailStr
    title: Optional[str] = None


class TeamBase(BaseModel):
    name: str
    description: Optional[str] = None
    members: List[TeamMember] = Field(default_factory=list)


class TeamCreate(TeamBase):
    pass


class TeamUpdate(TeamBase):
    pass


class TeamRead(TeamBase):
    id: int

    class Config:
        from_attributes = True


class ToolAccessCreate(BaseModel):
    tool_id: int
    tool_title: str
    action: Literal["open_tool", "view_modal"]
    user_email: Optional[EmailStr] = None


class ToolAccessRead(ToolAccessCreate):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True


class AnalyticsSummary(BaseModel):
    total_interactions: int
    total_views: int
    total_opens: int
    top_tools: List[dict]
    recent_activity: List[ToolAccessRead]
