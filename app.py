"""MANO ✦ — Personal AI hackathon demo. Real inference needs Nebius credentials.

Never run MANO_DATA_MODE=local on a shared/public host without accounts and
separate storage: local mode intentionally uses one unencrypted personal DB.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from mano_core import (
    accept_proposal, add_commitment, add_message, add_proposals, add_time_block,
    ask_nemotron, build_rescue_plan, calendar_ics, connect, erase_data, export_data, import_data,
    list_commitments, list_drafts, list_time_blocks, load_demo_scenario,
    mark_done, now_local, pending_proposals, radar, recent_messages,
    reject_proposal, remove_time_block, tavily_research,
)

st.set_page_config(page_title="MANO ✦ | Make room for life", page_icon="✦", layout="wide")
st.markdown("""
<style>
    .block-container {max-width: 1280px; padding-top: 1.2rem; padding-bottom: 2.5rem;}
    h1,h2,h3 {letter-spacing: -.045em;}
    h1 {font-size: 2.7rem !important; line-height: 1.08 !important;}
    [data-testid="stSidebar"] {border-right: 1px solid rgba(120,130,155,.15);}
    [data-testid="stMetric"] {padding: 1rem; border: 1px solid rgba(140,145,160,.2);
        border-radius: 17px; background: rgba(133,151,180,.035);}
    [data-testid="stChatMessage"] {border-radius: 16px; margin: .45rem 0;}
    .eyebrow {font-size:.77rem; text-transform: uppercase; letter-spacing:.16em;
        font-weight: 700; opacity:.65;}
    .subline {font-size:1.01rem; opacity:.73; max-width: 630px;}
    .small-label {font-size:.86rem; opacity:.7;}
    div.stButton button {border-radius: 11px;}
    section[data-testid="stSidebar"] div.stButton button {width:100%;}
</style>
""", unsafe_allow_html=True)

if "conn" not in st.session_state:
    mode = os.getenv("MANO_DATA_MODE", "demo").strip().lower()
    if mode not in {"demo", "local"}:
        st.error("MANO_DATA_MODE must be 'demo' or 'local'.")
        st.stop()
    path = str(Path(os.getenv("MANO_DB_PATH", "mano_private.db"))) if mode == "local" else ":memory:"
    st.session_state.conn = connect(path)

conn = st.session_state.conn
key_is_set = bool(os.getenv("NEBIUS_API_KEY", "").strip())
# A basic demo safety rail, not an authentication or global rate-limit system.
try:
    max_calls = max(1, int(os.getenv("MANO_MAX_CALLS_PER_SESSION", "10")))
except ValueError:
    max_calls = 10
if "inference_calls" not in st.session_state:
    st.session_state.inference_calls = 0
calls_left = max(0, max_calls - st.session_state.inference_calls)
can_chat = key_is_set and calls_left > 0
all_tasks = list_commitments(conn)
blocks = list_time_blocks(conn)
summary = radar(conn)

with st.sidebar:
    st.markdown("## MANO ✦")
    st.caption("Your world, a little less overwhelming.")
    st.divider()
    st.markdown("**AI connection**")
    if key_is_set:
        st.success("Nemotron configured via Nebius", icon="✅")
    else:
        st.warning("Add a Nebius API key for live chat", icon="⚠️")
    st.caption("The AI runs only when you send a message. No responses are simulated.")
    st.caption(f"Demo usage: {calls_left} AI requests left in this browser session. This is not a global cost cap.")
    st.divider()
    st.markdown("**Demo controls**")
    if st.button("✦ Load fictional student week", use_container_width=True):
        load_demo_scenario(conn)
        st.rerun()
    st.caption("Creates clearly fictional dated chat history and one overlapping schedule.")
    st.divider()
    st.markdown("**Your data**")
    st.download_button("Download my data (.json)", data=export_data(conn),
                       file_name="mano-data.json", mime="application/json", use_container_width=True)
    with st.expander("Restore a personal memory backup"):
        st.caption("This is optional, user-controlled portability. It replaces your current session, and does not automatically sync across visits.")
        uploaded_backup = st.file_uploader("Select your previous MANO export (.json)", type=["json"], key="mano_restore")
        confirm_import = st.checkbox("Replace all data in this session with my backup", key="mano_confirm_import")
        if st.button("Restore my MANO data", disabled=not (uploaded_backup and confirm_import), use_container_width=True):
            try:
                result = import_data(conn, uploaded_backup.getvalue())
            except Exception as exc:
                st.error(f"Could not restore backup: {exc}")
            else:
                st.success(f"Restored {result['messages']} conversation messages and {result['commitments']} commitments.")
                st.rerun()
    confirm_reset = st.checkbox("I want to erase this session's data")
    if st.button("Erase local MANO data", disabled=not confirm_reset, use_container_width=True):
        erase_data(conn)
        st.rerun()
    st.caption("Demo: isolated browser-session memory; lost on refresh/new session. Local: persistent unencrypted SQLite on your own machine. Never host local mode publicly without authentication.")
    st.divider()
    st.caption("MANO cannot send messages, edit external calendars, or notify you in the background. Calendar files need to be imported.")

now = now_local()
st.markdown("<div class='eyebrow'>PERSONAL AI · NVIDIA × NEBIUS</div>", unsafe_allow_html=True)
st.title("Make room for life. ✦")
st.markdown("<div class='subline'>Classes, careers, work, people, plans. Tell MANO what's happening. It keeps the pieces connected and helps you act on what matters.</div>", unsafe_allow_html=True)
st.caption(f"{now.strftime('%A, %B %-d')} · {os.getenv('MANO_TIMEZONE', 'America/Chicago').replace('_',' ')} · Your actions require approval")

metric1, metric2, metric3 = st.columns(3)
metric1.metric("Deadlines this week", len(summary["upcoming"]))
metric2.metric("Schedule collisions", len(summary["conflicts"]))
metric3.metric("Waiting for your approval", len(pending_proposals(conn)))

with st.expander("🧭 Rescue Studio — turn deadlines into a realistic plan", expanded=True):
    st.caption("Choose when you're *potentially* available. MANO will find open slots around the schedule you've saved, prioritize earlier deadlines and stage a plan for your approval. This is not connected to your external calendars.")
    p1, p2, p3, p4 = st.columns([1.1, .8, 1, 1.1])
    with p1:
        plan_start = st.date_input("Plan from", value=now.date(), key="rescue_start")
    with p2:
        plan_days = st.selectbox("Days", [1, 2, 3, 5, 7], index=1, key="rescue_days")
    with p3:
        available_from = st.time_input("Available from", value=datetime.strptime("09:00", "%H:%M").time(), key="rescue_from")
    with p4:
        available_to = st.time_input("Available until", value=datetime.strptime("21:00", "%H:%M").time(), key="rescue_to")
    focus_minutes = st.select_slider("Minutes per focus block (editable estimate)", options=[30, 45, 60, 90, 120], value=60)
    if st.button("Build my rescue plan", type="primary"):
        try:
            st.session_state.rescue_plan = build_rescue_plan(
                conn, plan_start, plan_days,
                available_from.strftime("%H:%M"), available_to.strftime("%H:%M"),
                focus_minutes=focus_minutes,
                max_blocks=4,
            )
        except ValueError as exc:
            st.error(str(exc))
    plan = st.session_state.get("rescue_plan")
    if plan:
        st.write(f"**Tentative plan:** {len(plan['proposals'])} focus blocks from {plan['considered']} unscheduled commitments")
        for proposal in plan["proposals"]:
            with st.container(border=True):
                st.markdown(f"**{proposal['title']}**")
                st.caption(f"{proposal['start_at'].replace('T',' ')} to {proposal['end_at'][11:16]} · {proposal['details']}")
        if plan["unscheduled"]:
            st.warning("No free slot found within your selected window for: " + ", ".join(plan["unscheduled"]))
        st.caption(plan["note"])
        if plan["proposals"]:
            if st.button("Stage these blocks for my approval", type="primary"):
                count = add_proposals(conn, plan["proposals"])
                del st.session_state["rescue_plan"]
                if count:
                    st.success(f"{count} new blocks staged. Review each one under 'Ready when you are'.")
                else:
                    st.info("Those blocks are already saved or awaiting approval. Nothing duplicated.")
                st.rerun()

main, side = st.columns([1.75, 1], gap="large")

with side:
    st.markdown("### Your radar")
    if summary["overdue"]:
        st.error(f"{len(summary['overdue'])} overdue commitment(s) need attention.")
    if summary["conflicts"]:
        st.warning(f"{len(summary['conflicts'])} schedule overlap(s) found.")
        with st.expander("See the conflicts", expanded=True):
            for c in summary["conflicts"]:
                st.markdown(f"**{c['first']}** overlaps **{c['second']}**")
                st.caption(f"{c['overlap_start'].replace('T', ' ')} – {c['overlap_end'][11:16]}")
    elif blocks:
        st.success("No overlapping time blocks in the saved schedule.")
    st.markdown("#### Commitments")
    if not all_tasks:
        st.caption("No tasks saved. Start a conversation, or add a task below.")
    else:
        for task in all_tasks[:14]:
            due = f" · {task['due_at'].replace('T', ' ')}" if task["due_at"] else ""
            if st.checkbox(task["title"] + due, key=f"task_{task['id']}"):
                mark_done(conn, task["id"])
                st.rerun()
    if blocks:
        st.markdown("#### Time blocks")
        for block in blocks[:10]:
            with st.container(border=True):
                st.write(f"**{block['title']}**")
                st.caption(f"{block['start_at'].replace('T', ' ')} – {block['end_at'][11:16]}")
                if st.button("Remove", key="remove_"+block["id"], type="tertiary"):
                    remove_time_block(conn, block["id"])
                    st.rerun()
    with st.expander("+ Add a task manually"):
        with st.form("add_task_form"):
            title = st.text_input("Task", placeholder="Finish CS assignment")
            include_deadline = st.checkbox("It has a deadline", value=True)
            due_date = st.date_input("Due date", value=now.date(), disabled=not include_deadline)
            due_time = st.time_input("Due time", value=datetime.strptime("18:00", "%H:%M").time(), disabled=not include_deadline)
            if st.form_submit_button("Save task", use_container_width=True):
                if not title.strip():
                    st.error("Give the task a title.")
                else:
                    due_at = datetime.combine(due_date, due_time).strftime("%Y-%m-%dT%H:%M") if include_deadline else None
                    add_commitment(conn, title.strip(), due_at)
                    st.rerun()
    if any(c["due_at"] for c in all_tasks) or blocks:
        st.download_button("Export calendar reminders (.ics)", data=calendar_ics(all_tasks, blocks),
                           file_name="mano-reminders.ics", mime="text/calendar", use_container_width=True)
        st.caption("Import into Apple/Google Calendar to activate reminders. Downloading does not schedule a notification.")

    proposals = pending_proposals(conn)
    if proposals:
        st.divider()
        st.markdown("### Ready when you are")
        st.caption("Nothing happens without your approval.")
        for item in proposals:
            p = item["payload"]
            with st.container(border=True):
                if item["kind"] == "add_task":
                    st.write("**Add task:** " + p["title"])
                    st.caption("Due: " + (p["due_at"] or "no date specified"))
                elif item["kind"] == "schedule_block":
                    st.write("**Reserve time:** " + p["title"])
                    st.caption(f"{p['start_at']} → {p['end_at']}")
                elif item["kind"] == "draft_email":
                    st.write("**Prepare email:** " + p["subject"])
                    with st.expander("Read the draft"):
                        st.write(p["body"])
                elif item["kind"] == "research":
                    st.write("**Research:** " + p["query"])
                yes, no = st.columns(2)
                with yes:
                    if st.button("Approve", key="accept_"+item["id"], use_container_width=True, type="primary"):
                        if item["kind"] == "research":
                            try:
                                results = tavily_research(p["query"])
                                lines = [f"- [{r['title']}]({r['url']}) — {r['snippet']}" for r in results]
                                add_message(conn, "assistant", "Here are sources I found:\n" + "\n".join(lines))
                            except Exception as exc:
                                st.error(f"Research failed: {exc}")
                                st.stop()
                        accept_proposal(conn, item["id"])
                        st.rerun()
                with no:
                    if st.button("Dismiss", key="reject_"+item["id"], use_container_width=True):
                        reject_proposal(conn, item["id"])
                        st.rerun()

with main:
    st.markdown("### Talk to MANO")
    a, b, c = st.columns(3)
    with a:
        brief_clicked = st.button("☀️ Brief my day", use_container_width=True, disabled=not can_chat)
    with b:
        rescue_clicked = st.button("🧭 Rescue my week", use_container_width=True, disabled=not can_chat)
    with c:
        recall_clicked = st.button("↩️ Yesterday's recap", use_container_width=True, disabled=not can_chat)
    quick_prompt = (
        "Give me an accurate briefing of the deadlines and commitments you know about, including any confirmed overlaps. Offer only actionable help you can really provide." if brief_clicked else
        "Review my saved commitments and deadline conflicts. Tell me which one to prioritize, and explain that I can build a tentative no-overlap schedule in Rescue Studio using the availability hours I select." if rescue_clicked else
        "What were we talking about yesterday? Give a factual summary and mention if there is no conversation from yesterday." if recall_clicked else None
    )
    history = recent_messages(conn, 35)
    if not history:
        with st.container(border=True):
            st.write("**Start anywhere. No setup questions needed.**")
            st.write("“I have an exam Friday, I work tomorrow, and I promised my club a presentation. Help me figure out what to do.”")
            st.write("“Can you draft a polite email to my professor?”")
            st.write("“Remember what we decided about my internship applications?”")
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    prompt = st.chat_input("What's happening in your world?", disabled=not can_chat)
    if not key_is_set:
        st.info("Add `NEBIUS_API_KEY` to your local `.env` and restart for real conversations. The fictional week and conflict detection work offline.")
    elif calls_left <= 0:
        st.warning("This browser session has reached its demo request limit. Offline features are still available.")
    chosen_prompt = prompt or quick_prompt
    if chosen_prompt and not can_chat:
        st.warning("Live chat isn't available. Check Nebius configuration or the session's demo limit.")
    elif chosen_prompt:
        st.session_state.inference_calls += 1
        add_message(conn, "user", chosen_prompt)
        try:
            with st.spinner("MANO is thinking..."):
                answer, new_actions = ask_nemotron(conn, chosen_prompt)
        except Exception as exc:
            st.error(f"Nebius inference failed: {exc}")
            st.caption("No pretend AI response has been substituted. Check your API key, model ID, credits and connectivity.")
        else:
            add_message(conn, "assistant", answer)
            add_proposals(conn, new_actions)
            st.rerun()

    st.divider()
    st.markdown("### Prepared email drafts")
    drafts = list_drafts(conn)
    if not drafts:
        st.caption("When you approve an email draft, it will appear here. MANO never sends it without a separate email integration.")
    else:
        for draft in drafts:
            with st.expander(draft["subject"]):
                st.text_area("Draft text", draft["body"], key="draft_"+draft["id"], height=170)
                st.caption("Saved only in this MANO data store; not sent.")

st.divider()
st.caption("MANO · Hackathon MVP · NVIDIA Nemotron via Nebius Token Factory · Student control first · Synthetic demo available")
