"""MANO web app: a chat-first companion on top of mano_core and mano_agent.

Run locally:   uvicorn server:app --reload    then open http://localhost:8000

Data modes (MANO_DATA_MODE):
  local  one private SQLite file on your own computer (MANO_DB_PATH). Use this for yourself.
  demo   hosted default. Each browser gets its own SQLite file, keyed by a random cookie,
         so a visitor's data survives reloads and revisits on that browser but is never
         shared. Files live in MANO_SESSION_DIR and disappear if the server restarts.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="MANO %(levelname)s: %(message)s")

from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import mano_agent as agent
import mano_core as core

ROOT = Path(__file__).parent
WEB = ROOT / "web"
MODE = os.getenv("MANO_DATA_MODE", "demo").strip().lower()
LOCAL_DB = os.getenv("MANO_DB_PATH", "mano_private.db")
SESSION_DIR = Path(os.getenv("MANO_SESSION_DIR", "/tmp/mano-sessions"))
COOKIE = "mano_sid"
SID_RE = re.compile(r"^[0-9a-f]{32}$")


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default)))
    except ValueError:
        return default


# Hosted safety rails. Local mode is your own key on your own machine, so no per-session cap there.
PER_SESSION_PER_DAY = _int_env("MANO_MAX_CALLS_PER_SESSION", 15)
GLOBAL_PER_DAY = _int_env("MANO_MAX_CALLS_PER_DAY", 400)
_global_usage: dict[str, int] = {}
_global_lock = threading.Lock()

app = FastAPI(title="MANO", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=WEB), name="static")


# ---------------------------------------------------------------- sessions

def _db_path(sid: str) -> str:
    if MODE == "local":
        return LOCAL_DB
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return str(SESSION_DIR / f"{sid}.db")


def _session(request: Request, response: Response | None = None) -> str:
    sid = request.cookies.get(COOKIE, "")
    if not SID_RE.match(sid):
        sid = uuid.uuid4().hex
        if response is not None:
            response.set_cookie(COOKIE, sid, max_age=60 * 60 * 24 * 180, httponly=True, samesite="lax")
    return sid


def _open(request: Request, response: Response | None = None):
    if MODE not in {"demo", "local"}:
        raise HTTPException(500, "MANO_DATA_MODE must be 'demo' or 'local'.")
    return core.connect(_db_path(_session(request, response)))


def _today() -> str:
    return core.now_local().date().isoformat()


def _calls_left(conn) -> int:
    if MODE == "local":
        return 999
    row = conn.execute("SELECT calls FROM usage WHERE day=?", (_today(),)).fetchone()
    return max(0, PER_SESSION_PER_DAY - (row["calls"] if row else 0))


def _spend_call(conn) -> None:
    """Count one AI request, or refuse if a limit is reached."""
    day = _today()
    with _global_lock:
        if _global_usage.get(day, 0) >= GLOBAL_PER_DAY:
            raise HTTPException(429, "MANO has reached today's limit for the public demo. Please try again tomorrow.")
        if _calls_left(conn) <= 0:
            raise HTTPException(429, "You've used today's AI requests for this demo. Everything else still works.")
        _global_usage[day] = _global_usage.get(day, 0) + 1
    if MODE != "local":
        conn.execute("INSERT INTO usage (day, calls) VALUES (?,1) ON CONFLICT(day) DO UPDATE SET calls=calls+1", (day,))
        conn.commit()


def _require_ai() -> None:
    if not os.getenv("NEBIUS_API_KEY", "").strip():
        raise HTTPException(503, "MANO's AI isn't connected. Add NEBIUS_API_KEY to .env and restart.")


def _require_web() -> None:
    if not os.getenv("TAVILY_API_KEY", "").strip():
        raise HTTPException(503, "Web search isn't connected. Add TAVILY_API_KEY to .env and restart.")


# ---------------------------------------------------------------- state

def _state(conn) -> dict:
    steps = core.steps_by_message(conn)
    messages = [{**m, "steps": steps.get(m["id"], [])} for m in core.recent_messages(conn, 60)]
    r = core.radar(conn)
    label = lambda v: core.when_label(v)
    tasks = [{**t, "due_label": label(t["due_at"])} for t in core.list_commitments(conn)]
    clock = lambda v: label(v).split(", ")[-1]
    blocks = [{**b, "start_label": label(b["start_at"]), "end_time": clock(b["end_at"])} for b in core.list_time_blocks(conn)]
    conflicts = [{**c, "when": f"{label(c['overlap_start'])} to {clock(c['overlap_end'])}"} for c in r["conflicts"]]
    return {
        "profile": core.get_profile(conn),
        "profile_fields": [{"key": k, "label": v[0], "limit": v[1]} for k, v in core.PROFILE_FIELDS.items()],
        "greeting": core.greeting(conn),
        "onboarding": core.onboarding_step(conn),
        "messages": messages,
        "tasks": tasks,
        "blocks": blocks,
        "radar": {"overdue": len(r["overdue"]), "upcoming": len(r["upcoming"]), "conflicts": conflicts},
        "proposals": core.pending_proposals(conn),
        "drafts": core.list_drafts(conn),
        "flags": {"ai": bool(os.getenv("NEBIUS_API_KEY", "").strip()),
                  "web": bool(os.getenv("TAVILY_API_KEY", "").strip()),
                  "mode": MODE, "calls_left": _calls_left(conn),
                  "model": os.getenv("NEBIUS_MODEL", core.MODEL)},
        "opportunity_kinds": agent.OPPORTUNITY_KINDS,
    }


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/state")
def state(request: Request, response: Response):
    conn = _open(request, response)
    try:
        return _state(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------- chat (live agent steps over SSE)

def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.post("/api/chat")
async def chat(request: Request, payload: dict = Body(...)):
    text = str(payload.get("text", "")).strip()
    if not text or len(text) > 4000:
        raise HTTPException(400, "Write a message of up to 4,000 characters.")
    response = Response()
    sid = _session(request, response)
    path = _db_path(sid)
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    if "set-cookie" in response.headers:
        headers["Set-Cookie"] = response.headers["set-cookie"]
    _require_ai()
    conn = core.connect(path)
    try:
        _spend_call(conn)
        core.start_conversation(conn)
        core.add_message(conn, "user", text)
        told = core.stated_name(text)  # "my name is…" at any point updates what MANO calls you
        if told:
            core.save_profile(conn, {"name": told})
    finally:
        conn.close()
    listen = bool(payload.get("listen"))
    events: queue.Queue = queue.Queue()

    def work():
        db = core.connect(path)
        try:
            reply, proposals, steps = agent.run_agent(
                db, text, friend_mode=True if (listen and not core.asks_for_help(text)) else None,
                on_event=lambda kind, data: events.put((kind, data)))
            message_id = core.add_message(db, "assistant", reply)
            core.save_steps(db, message_id, steps)
            core.add_proposals(db, proposals)
            events.put(("done", {"state": _state(db)}))
        except Exception as exc:  # shown to the student; never a fake reply
            logging.getLogger("mano").warning("Chat failed: %s: %s", type(exc).__name__, exc)
            events.put(("error", {"message": f"MANO couldn't answer just now: {exc}"[:400]}))
        finally:
            db.close()
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    async def stream():
        while True:
            item = await asyncio.to_thread(events.get)
            if item is None:
                return
            yield _sse(*item)

    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)


# ---------------------------------------------------------------- approvals

@app.post("/api/proposals/{proposal_id}/{decision}")
def decide(proposal_id: str, decision: str, request: Request, response: Response):
    conn = _open(request, response)
    try:
        pending = {p["id"]: p for p in core.pending_proposals(conn)}
        if proposal_id not in pending:
            raise HTTPException(404, "That suggestion was already handled.")
        if decision == "dismiss":
            core.reject_proposal(conn, proposal_id)
            return {"message": "Okay, set aside.", "state": _state(conn)}
        if decision != "approve":
            raise HTTPException(400, "Use approve or dismiss.")
        p = pending[proposal_id]
        if p["kind"] == "research":
            _require_web()
            results = core.tavily_research(p["payload"]["query"])
            lines = [f"- [{r['title'] or r['url']}]({r['url']}): {r['snippet']}" for r in results]
            core.add_message(conn, "assistant", "Here's what I found:\n\n" + ("\n".join(lines) or "Nothing useful turned up."))
        message = core.accept_proposal(conn, proposal_id)
        return {"message": message, "state": _state(conn)}
    finally:
        conn.close()


# ---------------------------------------------------------------- your week

@app.put("/api/profile")
def profile(request: Request, response: Response, payload: dict = Body(...)):
    conn = _open(request, response)
    try:
        core.save_profile(conn, {k: v for k, v in payload.items() if k in core.PROFILE_FIELDS and isinstance(v, str)})
        return _state(conn)
    finally:
        conn.close()


@app.post("/api/tasks")
def add_task(request: Request, response: Response, payload: dict = Body(...)):
    title = str(payload.get("title", "")).strip()
    due = payload.get("due_at") or None
    if not title:
        raise HTTPException(400, "Give the task a name.")
    conn = _open(request, response)
    try:
        if due:
            core._parse_wall_time(str(due))
        core.add_commitment(conn, title, due, str(payload.get("category", "personal"))[:60])
        return _state(conn)
    except ValueError:
        raise HTTPException(400, "Use a date and time like 2026-10-31T18:00.")
    finally:
        conn.close()


@app.post("/api/tasks/{task_id}/done")
def task_done(task_id: str, request: Request, response: Response):
    conn = _open(request, response)
    try:
        core.mark_done(conn, task_id)
        return _state(conn)
    finally:
        conn.close()


@app.delete("/api/blocks/{block_id}")
def remove_block(block_id: str, request: Request, response: Response):
    conn = _open(request, response)
    try:
        core.remove_time_block(conn, block_id)
        return _state(conn)
    finally:
        conn.close()


@app.get("/api/calendar.ics")
def calendar(request: Request, response: Response):
    conn = _open(request, response)
    try:
        body = core.calendar_ics(core.list_commitments(conn), core.list_time_blocks(conn))
    finally:
        conn.close()
    return Response(body, media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="mano-week.ics"'})


# ---------------------------------------------------------------- the world: news and opportunities

@app.post("/api/briefing")
def briefing(request: Request, response: Response):
    _require_ai(); _require_web()
    conn = _open(request, response)
    try:
        topics = core.interest_topics(core.get_profile(conn))
        if not topics:
            raise HTTPException(400, "Tell me a few topics you care about in About you, and I'll bring you the news on them.")
        _spend_call(conn)
        result = core.personalized_briefing(conn)
        core.add_message(conn, "user", "What's happening in the world on " + ", ".join(topics) + "?")
        core.add_message(conn, "assistant", result["text"])
        return _state(conn)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    finally:
        conn.close()


@app.post("/api/opportunities")
def opportunities(request: Request, response: Response, payload: dict = Body(...)):
    _require_ai(); _require_web()
    kind = str(payload.get("kind", "internships"))
    if kind not in agent.OPPORTUNITY_KINDS:
        raise HTTPException(400, "Pick internships, scholarships, events, research or hackathons.")
    conn = _open(request, response)
    try:
        _spend_call(conn)
        result = agent.opportunity_radar(conn, kind, str(payload.get("focus", ""))[:120])
        return {**result, "calls_left": _calls_left(conn)}
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    finally:
        conn.close()


@app.post("/api/opportunities/track")
def track(request: Request, response: Response, payload: dict = Body(...)):
    item = payload.get("item") or {}
    if not isinstance(item.get("title"), str) or not str(item.get("url", "")).startswith("http"):
        raise HTTPException(400, "That opportunity is missing a title or link.")
    deadline = item.get("deadline")
    try:
        deadline = datetime.fromisoformat(deadline).date().isoformat() if deadline else None
    except (TypeError, ValueError):
        deadline = None
    clean = {"title": item["title"][:160], "url": item["url"][:500],
             "organization": str(item.get("organization") or "")[:120], "deadline": deadline}
    conn = _open(request, response)
    try:
        added = core.add_proposals(conn, [agent.opportunity_task(clean)])
        return {"added": bool(added), "state": _state(conn)}
    finally:
        conn.close()


# ---------------------------------------------------------------- your data

@app.post("/api/fresh-chat")
def fresh_chat(request: Request, response: Response):
    conn = _open(request, response)
    try:
        core.clear_conversation(conn)
        return _state(conn)
    finally:
        conn.close()


@app.post("/api/sample-week")
def sample_week(request: Request, response: Response):
    conn = _open(request, response)
    try:
        core.erase_data(conn)
        core.load_demo_scenario(conn)
        return _state(conn)
    finally:
        conn.close()


@app.get("/api/export")
def export(request: Request, response: Response):
    conn = _open(request, response)
    try:
        body = core.export_data(conn)
    finally:
        conn.close()
    return Response(body, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="mano-data.json"'})


@app.post("/api/import")
async def restore(request: Request):
    data = await request.body()
    response = Response()
    conn = _open(request, response)
    try:
        counts = core.import_data(conn, data)
        result = JSONResponse({"counts": counts, "state": _state(conn)})
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    finally:
        conn.close()
    if "set-cookie" in response.headers:
        result.headers["set-cookie"] = response.headers["set-cookie"]
    return result


@app.post("/api/erase")
def erase(request: Request, response: Response):
    conn = _open(request, response)
    try:
        core.erase_data(conn)
        return _state(conn)
    finally:
        conn.close()
