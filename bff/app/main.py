from __future__ import annotations

import io
from typing import List, Optional

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import OnboardingTool, Team, ToolAccess
from .schemas import (
    AnalyticsSummary,
    TeamCreate,
    TeamRead,
    TeamUpdate,
    ToolAccessCreate,
    ToolAccessRead,
    ToolBulkRequest,
    ToolCreate,
    ToolRead,
    ToolUpdate,
)

app = FastAPI(title="Application Catalog BFF", docs_url="/api/docs", redoc_url=None)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


def _tool_query(db: Session, search: Optional[str], category: Optional[str], status: Optional[str]):
    query = db.query(OnboardingTool)
    if search:
        like_value = f"%{search}%"
        query = query.filter(
            (OnboardingTool.title.ilike(like_value)) | (OnboardingTool.category.ilike(like_value))
        )
    if category:
        query = query.filter(OnboardingTool.category == category)
    if status:
        query = query.filter(OnboardingTool.status == status)
    return query


@app.get("/tools", response_model=List[ToolRead])
def list_tools(
    search: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = _tool_query(db, search, category, status)
    tools = (
        query.order_by(
            OnboardingTool.is_featured.desc(),
            OnboardingTool.sort_order.asc(),
            OnboardingTool.title.asc(),
        ).all()
    )
    return tools


@app.post("/tools", response_model=ToolRead)
def create_tool(tool: ToolCreate, db: Session = Depends(get_db)):
    existing = db.query(OnboardingTool).filter(OnboardingTool.title == tool.title).first()
    if existing:
        raise HTTPException(status_code=400, detail="Title must be unique.")
    record = OnboardingTool(**tool.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.post("/tools/bulk", response_model=List[ToolRead])
def bulk_create_tools(payload: ToolBulkRequest, db: Session = Depends(get_db)):
    created = []
    for tool in payload.tools:
        existing = db.query(OnboardingTool).filter(OnboardingTool.title == tool.title).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Title already exists: {tool.title}")
        record = OnboardingTool(**tool.model_dump())
        db.add(record)
        created.append(record)
    db.commit()
    for record in created:
        db.refresh(record)
    return created


@app.get("/tools/{tool_id}", response_model=ToolRead)
def get_tool(tool_id: int, db: Session = Depends(get_db)):
    tool = db.query(OnboardingTool).filter(OnboardingTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found.")
    return tool


@app.put("/tools/{tool_id}", response_model=ToolRead)
def update_tool(tool_id: int, tool: ToolUpdate, db: Session = Depends(get_db)):
    record = db.query(OnboardingTool).filter(OnboardingTool.id == tool_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Tool not found.")
    duplicate = (
        db.query(OnboardingTool)
        .filter(OnboardingTool.title == tool.title, OnboardingTool.id != tool_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Title must be unique.")
    for key, value in tool.model_dump().items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


@app.put("/tools/by-title/{title}", response_model=ToolRead)
def update_tool_by_title(title: str, tool: ToolUpdate, db: Session = Depends(get_db)):
    record = db.query(OnboardingTool).filter(OnboardingTool.title == title).first()
    if not record:
        raise HTTPException(status_code=404, detail="Tool not found.")
    duplicate = (
        db.query(OnboardingTool)
        .filter(OnboardingTool.title == tool.title, OnboardingTool.id != record.id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Title must be unique.")
    for key, value in tool.model_dump().items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


@app.delete("/tools/{tool_id}")
def delete_tool(tool_id: int, db: Session = Depends(get_db)):
    record = db.query(OnboardingTool).filter(OnboardingTool.id == tool_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Tool not found.")
    db.delete(record)
    db.commit()
    return {"status": "deleted"}


@app.post("/tools/{tool_id}/logo/upload")
def upload_logo(tool_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    record = db.query(OnboardingTool).filter(OnboardingTool.id == tool_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Tool not found.")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Logo must be an image file.")
    record.logo_data = file.file.read()
    record.logo_content_type = file.content_type
    db.commit()
    return {"status": "uploaded"}


@app.post("/tools/{tool_id}/logo/import")
def import_logo(tool_id: int, url: str = Query(...), db: Session = Depends(get_db)):
    record = db.query(OnboardingTool).filter(OnboardingTool.id == tool_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Tool not found.")
    with httpx.Client(timeout=10) as client:
        response = client.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Unable to fetch logo URL.")
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Logo URL must be an image.")
    record.logo_data = response.content
    record.logo_content_type = content_type
    db.commit()
    return {"status": "imported"}


@app.get("/logos/{tool_id}")
def get_logo(tool_id: int, db: Session = Depends(get_db)):
    record = db.query(OnboardingTool).filter(OnboardingTool.id == tool_id).first()
    if not record or not record.logo_data:
        raise HTTPException(status_code=404, detail="Logo not found.")
    return Response(content=record.logo_data, media_type=record.logo_content_type or "image/png")


@app.get("/teams", response_model=List[TeamRead])
def list_teams(db: Session = Depends(get_db)):
    return db.query(Team).order_by(Team.name.asc()).all()


@app.post("/teams", response_model=TeamRead)
def create_team(team: TeamCreate, db: Session = Depends(get_db)):
    existing = db.query(Team).filter(Team.name == team.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Team name must be unique.")
    record = Team(**team.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/teams/{team_id}", response_model=TeamRead)
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")
    return team


@app.put("/teams/{team_id}", response_model=TeamRead)
def update_team(team_id: int, team: TeamUpdate, db: Session = Depends(get_db)):
    record = db.query(Team).filter(Team.id == team_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Team not found.")
    duplicate = db.query(Team).filter(Team.name == team.name, Team.id != team_id).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Team name must be unique.")
    for key, value in team.model_dump().items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


@app.delete("/teams/{team_id}")
def delete_team(team_id: int, db: Session = Depends(get_db)):
    record = db.query(Team).filter(Team.id == team_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Team not found.")
    db.delete(record)
    db.commit()
    return {"status": "deleted"}


@app.post("/tool_access", response_model=ToolAccessRead)
def create_access_event(event: ToolAccessCreate, db: Session = Depends(get_db)):
    record = ToolAccess(**event.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/analytics", response_model=AnalyticsSummary)
def analytics(db: Session = Depends(get_db)):
    total_interactions = db.query(func.count(ToolAccess.id)).scalar() or 0
    total_views = (
        db.query(func.count(ToolAccess.id)).filter(ToolAccess.action == "view_modal").scalar() or 0
    )
    total_opens = (
        db.query(func.count(ToolAccess.id)).filter(ToolAccess.action == "open_tool").scalar() or 0
    )
    top_tools = (
        db.query(ToolAccess.tool_title, func.count(ToolAccess.id).label("count"))
        .group_by(ToolAccess.tool_title)
        .order_by(func.count(ToolAccess.id).desc())
        .limit(10)
        .all()
    )
    recent_activity = (
        db.query(ToolAccess)
        .order_by(ToolAccess.timestamp.desc())
        .limit(20)
        .all()
    )
    return AnalyticsSummary(
        total_interactions=total_interactions,
        total_views=total_views,
        total_opens=total_opens,
        top_tools=[{"tool_title": title, "count": count} for title, count in top_tools],
        recent_activity=recent_activity,
    )
