from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BFF_URL = os.getenv("BFF_URL", "http://localhost:8001")

app = FastAPI(title="Application Catalog UI")

app.mount("/static", StaticFiles(directory="ui/app/static"), name="static")

templates = Jinja2Templates(directory="ui/app/templates")


async def bff_request(method: str, path: str, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            return await client.request(method, f"{BFF_URL}{path}", **kwargs)
        except httpx.RequestError as exc:
            return httpx.Response(status_code=503, request=exc.request)


def _parse_form_list(value: str) -> list:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_owner_teams(value: str) -> list:
    if not value:
        return []
    return [int(item) for item in value.split(",") if item.strip().isdigit()]


def _parse_experts(value: str) -> list:
    experts = []
    if not value:
        return experts
    for line in value.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 2:
            experts.append(
                {
                    "name": parts[0],
                    "email": parts[1],
                    "title": parts[2] if len(parts) > 2 and parts[2] else None,
                    "is_backup": parts[3].lower() == "backup" if len(parts) > 3 else False,
                }
            )
    return experts


def _parse_docs(value: str) -> list:
    docs = []
    if not value:
        return docs
    for line in value.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 2:
            docs.append(
                {
                    "title": parts[0],
                    "url": parts[1],
                    "type": parts[2] if len(parts) > 2 and parts[2] else None,
                }
            )
    return docs


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, search: Optional[str] = None, category: Optional[str] = None, status: Optional[str] = None):
    response = await bff_request("GET", "/tools", params={"search": search, "category": category, "status": status})
    tools = response.json() if response.status_code == 200 else []
    categories = sorted({tool["category"] for tool in tools})
    status_counts = {
        "total": len(tools),
        "active": sum(1 for tool in tools if tool.get("status") == "Active"),
        "deprecated": sum(1 for tool in tools if tool.get("status") == "Deprecated"),
        "planned": sum(1 for tool in tools if tool.get("status") == "Planned"),
        "featured": sum(1 for tool in tools if tool.get("is_featured")),
    }
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "tools": tools,
            "categories": categories,
            "search": search or "",
            "category": category or "",
            "status": status or "",
            "status_counts": status_counts,
            "bff_url": BFF_URL,
        },
    )


@app.get("/tools/{tool_id}", response_class=HTMLResponse)
async def tool_detail(request: Request, tool_id: int):
    response = await bff_request("GET", f"/tools/{tool_id}")
    if response.status_code != 200:
        return templates.TemplateResponse("not_found.html", {"request": request}, status_code=404)
    tool = response.json()
    teams_response = await bff_request("GET", "/teams")
    teams = teams_response.json() if teams_response.status_code == 200 else []
    team_lookup = {team["id"]: team["name"] for team in teams}
    owner_team_names = [team_lookup.get(team_id, f"Team #{team_id}") for team_id in tool.get("owner_teams", [])]
    await bff_request(
        "POST",
        "/tool_access",
        json={"tool_id": tool_id, "tool_title": tool["title"], "action": "view_modal"},
    )
    return templates.TemplateResponse(
        "tool_detail.html",
        {
            "request": request,
            "tool": tool,
            "owner_team_names": owner_team_names,
            "bff_url": BFF_URL,
        },
    )


@app.get("/manage/tools", response_class=HTMLResponse)
async def manage_tools(request: Request, error: Optional[str] = None):
    tools_response = await bff_request("GET", "/tools")
    teams_response = await bff_request("GET", "/teams")
    tools = tools_response.json() if tools_response.status_code == 200 else []
    teams = teams_response.json() if teams_response.status_code == 200 else []
    error_message = None
    if error == "update":
        error_message = "Unable to update tool. Please check the values and try again."
    return templates.TemplateResponse(
        "manage_tools.html",
        {"request": request, "tools": tools, "teams": teams, "error": error_message, "form_values": {}},
    )


@app.post("/manage/tools")
async def create_tool(
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    tags: str = Form(""),
    owner_teams: str = Form(""),
    access_owner_name: str = Form(""),
    access_owner_email: str = Form(""),
    access_process: str = Form(""),
    tool_url: str = Form(""),
    experts: str = Form(""),
    documentation_links: str = Form(""),
    status: str = Form("Active"),
    sort_order: int = Form(0),
    is_featured: Optional[bool] = Form(False),
):
    payload: Dict[str, Any] = {
        "title": title,
        "category": category,
        "description": description,
        "tags": _parse_form_list(tags),
        "owner_teams": _parse_owner_teams(owner_teams),
        "access_owner_name": access_owner_name or None,
        "access_owner_email": access_owner_email or None,
        "access_process": access_process or None,
        "tool_url": tool_url or None,
        "experts": _parse_experts(experts),
        "documentation_links": _parse_docs(documentation_links),
        "status": status,
        "sort_order": sort_order,
        "is_featured": bool(is_featured),
    }
    response = await bff_request("POST", "/tools", json=payload)
    if response.status_code != 200:
        tools_response = await bff_request("GET", "/tools")
        teams_response = await bff_request("GET", "/teams")
        tools = tools_response.json() if tools_response.status_code == 200 else []
        teams = teams_response.json() if teams_response.status_code == 200 else []
        try:
            detail = response.json().get("detail", "Unable to create tool.")
            if isinstance(detail, list):
                error_message = "Validation error: " + ", ".join(item.get("msg", "Invalid value") for item in detail)
            else:
                error_message = detail
        except ValueError:
            error_message = "Unable to create tool."
        return templates.TemplateResponse(
            "manage_tools.html",
            {
                "request": request,
                "tools": tools,
                "teams": teams,
                "error": error_message,
                "form_values": {
                    "title": title,
                    "category": category,
                    "description": description,
                    "tags": tags,
                    "owner_teams": owner_teams,
                    "access_owner_name": access_owner_name,
                    "access_owner_email": access_owner_email,
                    "access_process": access_process,
                    "tool_url": tool_url,
                    "experts": experts,
                    "documentation_links": documentation_links,
                    "status": status,
                    "sort_order": sort_order,
                    "is_featured": is_featured,
                },
            },
            status_code=400,
        )
    return RedirectResponse("/manage/tools", status_code=303)


@app.post("/manage/tools/{tool_id}/delete")
async def delete_tool(tool_id: int):
    await bff_request("DELETE", f"/tools/{tool_id}")
    return RedirectResponse("/manage/tools", status_code=303)


@app.post("/manage/tools/{tool_id}/edit")
async def edit_tool(
    tool_id: int,
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    tags: str = Form(""),
    owner_teams: str = Form(""),
    access_owner_name: str = Form(""),
    access_owner_email: str = Form(""),
    access_process: str = Form(""),
    tool_url: str = Form(""),
    experts: str = Form(""),
    documentation_links: str = Form(""),
    status: str = Form("Active"),
    sort_order: int = Form(0),
    is_featured: Optional[bool] = Form(False),
):
    payload: Dict[str, Any] = {
        "title": title,
        "category": category,
        "description": description,
        "tags": _parse_form_list(tags),
        "owner_teams": _parse_owner_teams(owner_teams),
        "access_owner_name": access_owner_name or None,
        "access_owner_email": access_owner_email or None,
        "access_process": access_process or None,
        "tool_url": tool_url or None,
        "experts": _parse_experts(experts),
        "documentation_links": _parse_docs(documentation_links),
        "status": status,
        "sort_order": sort_order,
        "is_featured": bool(is_featured),
    }
    response = await bff_request("PUT", f"/tools/{tool_id}", json=payload)
    if response.status_code != 200:
        return RedirectResponse("/manage/tools?error=update", status_code=303)
    return RedirectResponse("/manage/tools", status_code=303)


@app.post("/manage/tools/{tool_id}/logo/upload")
async def upload_logo(tool_id: int, request: Request):
    form = await request.form()
    file = form.get("logo_file")
    files = {"file": (file.filename, file.file, file.content_type)} if file else None
    await bff_request("POST", f"/tools/{tool_id}/logo/upload", files=files)
    return RedirectResponse("/manage/tools", status_code=303)


@app.post("/manage/tools/{tool_id}/logo/import")
async def import_logo(tool_id: int, logo_url: str = Form(...)):
    await bff_request("POST", f"/tools/{tool_id}/logo/import", params={"url": logo_url})
    return RedirectResponse("/manage/tools", status_code=303)


@app.get("/manage/teams", response_class=HTMLResponse)
async def manage_teams(request: Request, error: Optional[str] = None):
    response = await bff_request("GET", "/teams")
    teams = response.json() if response.status_code == 200 else []
    error_message = None
    if error == "team":
        error_message = "Unable to create team. Please check the values and try again."
    if error == "update":
        error_message = "Unable to update team. Please check the values and try again."
    return templates.TemplateResponse(
        "manage_teams.html",
        {"request": request, "teams": teams, "error": error_message},
    )


@app.post("/manage/teams")
async def create_team(name: str = Form(...), description: str = Form(""), members: str = Form("")):
    parsed_members = []
    if members:
        for line in members.splitlines():
            parts = [part.strip() for part in line.split("|")]
            if len(parts) >= 2:
                parsed_members.append(
                    {
                        "name": parts[0],
                        "email": parts[1],
                        "title": parts[2] if len(parts) > 2 else None,
                    }
                )
    payload = {"name": name, "description": description, "members": parsed_members}
    response = await bff_request("POST", "/teams", json=payload)
    if response.status_code != 200:
        return RedirectResponse("/manage/teams?error=team", status_code=303)
    return RedirectResponse("/manage/teams", status_code=303)


@app.post("/manage/teams/{team_id}/edit")
async def edit_team(team_id: int, name: str = Form(...), description: str = Form(""), members: str = Form("")):
    parsed_members = []
    if members:
        for line in members.splitlines():
            parts = [part.strip() for part in line.split("|")]
            if len(parts) >= 2:
                parsed_members.append(
                    {
                        "name": parts[0],
                        "email": parts[1],
                        "title": parts[2] if len(parts) > 2 else None,
                    }
                )
    payload = {"name": name, "description": description, "members": parsed_members}
    response = await bff_request("PUT", f"/teams/{team_id}", json=payload)
    if response.status_code != 200:
        return RedirectResponse("/manage/teams?error=update", status_code=303)
    return RedirectResponse("/manage/teams", status_code=303)


@app.post("/manage/teams/{team_id}/delete")
async def delete_team(team_id: int):
    await bff_request("DELETE", f"/teams/{team_id}")
    return RedirectResponse("/manage/teams", status_code=303)


@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    response = await bff_request("GET", "/analytics")
    data = response.json() if response.status_code == 200 else {}
    return templates.TemplateResponse("analytics.html", {"request": request, "data": data})


@app.post("/tools/{tool_id}/open")
async def open_tool(tool_id: int, tool_url: str = Form(...), tool_title: str = Form(...)):
    if not tool_url:
        return RedirectResponse(f"/tools/{tool_id}", status_code=303)
    await bff_request(
        "POST",
        "/tool_access",
        json={"tool_id": tool_id, "tool_title": tool_title, "action": "open_tool"},
    )
    return RedirectResponse(tool_url, status_code=303)


@app.get("/logos/{tool_id}")
async def proxy_logo(tool_id: int):
    response = await bff_request("GET", f"/logos/{tool_id}")
    if response.status_code != 200:
        return Response(status_code=404)
    return Response(content=response.content, media_type=response.headers.get("content-type", "image/png"))
