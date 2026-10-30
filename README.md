# MANO ✦ — More life, less mental load

**NVIDIA × Nebius Global AI Hackathon (2026) · Personal AI track**

MANO is a student-focused personal AI: a mentor that knows your goals, a planner that spots real deadline and schedule conflicts, a news briefing tuned to your interests, and a friend that listens when you just need to vent. Recommendations become **approved** tasks, time blocks, email drafts, or source-grounded research, never silent actions.

> **Pitch:** Most apps help you track one part of your life. MANO connects them. When study, work, friendships and career goals collide, MANO helps you decide what matters and take the next step.

## What works in this MVP

| Capability | Implementation | Requires API? |
|---|---|---|
| **Agent with reusable skills** | Nemotron chains up to 3 read-only skills (schedule check, past-conversation recall, focus planner, news, opportunity search, web research) before answering; every step is shown under the reply | Nebius key (+ Tavily for web skills) |
| **Opportunity Radar** | Live Tavily search for internships, scholarships, events, research programs and hackathons matched to the profile; Nemotron turns real results into source-linked cards; "Track this application" stages a deadline task | Nebius + Tavily keys |
| Goals profile ("About me") | Saved goals, school, interests, stressors and support style; fed into every conversation | No (to save) |
| Mentor-style guidance | Advice tied to your saved goals and actual commitments | Nebius key |
| Friend mode | "Just listen" toggle, plus automatic detection of venting; never stages tasks while listening | Nebius key |
| Personalized news briefing | Tavily news search on your saved interests, summarized by Nemotron with numbered sources | Nebius + Tavily keys |
| Actual AI conversations | NVIDIA Nemotron 3 Super on **Nebius Token Factory** OpenAI-compatible API | Nebius key |
| Recall prior conversations | SQLite dated history and topic-relevant retrieval, including yesterday recap | Nebius key for conversational reply |
| Private persistence | `MANO_DATA_MODE=local`, SQLite on the individual's own computer | No |
| Deadline radar | Flags overdue tasks and upcoming deadlines within seven days | No |
| Conflict radar | Finds overlapping saved start/end time blocks, with exact overlap window | No |
| Rescue Studio (new) | Deterministic deadline-first time blocking; checks saved events, stages non-overlapping proposals for approval | No |
| Rescue My Week chat | Agent reviews actual conflicts and suggests changes | Nebius key |
| Action proposals | Tasks, timed study blocks, email drafts, Tavily research; separate approval required | Nebius key to generate proposals |
| Saved tasks and time blocks | Approved tasks/blocks stored to SQLite; optional manual task entry | No |
| Calendar reminders | Download `.ics` files with 15-/30-minute display alarms | No |
| Email drafts | Stores drafts only; **never sends them** | Nebius key to generate |
| Data control | Export/restore a portable personal JSON backup; clear all local/session data | No |
| Duplicate-action protection | Prevents repeatedly queueing the same task or time block | No |
| Fictional demo scenario | Dated chat history + exams, workshop, overlapping meeting and shift | No |

The dashboard intentionally **does not** open with a monologue announcing memory features or require an explicit “remember this” command. Relevant previous conversations are automatically supplied when responding. Only action-taking requires approval.

## How MANO uses NVIDIA Nemotron and Nebius Token Factory

Every AI feature makes a runtime call to **NVIDIA Nemotron 3 Super** (`nvidia/nemotron-3-super-120b-a12b`) through the **Nebius Token Factory** OpenAI-compatible API, with JSON-mode output:

- **Agent loop** (`mano_agent.py`): Nemotron reads the student's profile, commitments and conflict radar, then decides which reusable skills to run, reads the results, and writes a grounded answer plus approval-gated proposals. The loop uses plain JSON turns, so it works on any Token Factory model with JSON output.
- **Mentor and friend modes**: the same model switches between goal-aware coaching and pure listening (no tasks) based on the message or the "Just listen" toggle.
- **Grounded summarization**: news briefings and Opportunity Radar cards are written by Nemotron from numbered search results only. The app rejects any card that doesn't point at a real result, and any deadline that's malformed or already past.
- **Why Token Factory**: one OpenAI-compatible endpoint meant no custom serving code, and switching models is a single environment variable (`NEBIUS_MODEL`), which made it quick to iterate on prompts and the agent protocol.

## How MANO uses Tavily

Tavily is MANO's window onto the world, always called at runtime and always cited:

1. **Opportunity Radar**: profile-aware queries (interests, school, location, the current application cycle) for internships, scholarships, events, research programs and hackathons.
2. **Personalized news briefing**: `topic: news` searches over the past week on each saved interest.
3. **Agent web skills**: `search_news`, `find_opportunities` and `web_research`, which Nemotron calls on its own when a question needs fresh information.
4. **Approved research proposals** from chat.

## Important limits and privacy

- Hosted `demo` mode gives each browser its own private SQLite file, keyed by a random cookie. MANO remembers you across reloads and visits on that browser, but nothing is shared between visitors, and the files are cleared if the server restarts. Download my data and Restore from a backup move your data between browsers.
- `local` mode preserves SQLite memory between sessions on a **trusted personal computer**. Do not switch public hosting to `local`: without authentication it could expose one person's records to another.
- The Rescue Studio checks **only** times saved inside MANO and the user-selected planning window. It cannot see Google/Apple Calendar, travel time, work changes, or actual outside availability. Review all proposed times before approval.
- Task/calendar actions are local to MANO until you approve them. Calendar exports require a separate import. MANO does **not** send push notifications, emails, or silently change external calendars.
- Public model calls can use the owner's Nebius credit balance; the per-session request cap is not global usage protection.

## Technical design

```text
Student -> MANO web app (web/) -> FastAPI (server.py) -> context assembly
                                  |— dated conversation history / topic retrieval
                                  |— assignments + deadlines (SQLite)
                                  |— scheduled blocks + deterministic conflict radar
                             NVIDIA Nemotron 3 Super
                             via Nebius Token Factory
                             agent loop: chains up to 3 read-only skills,
                             each step streamed live to the browser (SSE)
                                      |
                        Answer + validated proposed actions
                                      |
                              Student approval
                        /            |             \
                 Save task       Save email     Research via Tavily
                 / time block    draft          (optional key)
                        |
                      .ics export -> import to calendar for device alerts
```

### Get started (Mac)

Use **Python 3.11–3.13**. Extract the ZIP, open Terminal, and run:

```bash
cd MANO-GitHub-Release
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Get a Nebius Token Factory API key from the Token Factory console. Add it to your **local** `.env`:

```ini
NEBIUS_API_KEY=your_nebius_key_here
NEBIUS_BASE_URL=https://api.tokenfactory.us-central1.nebius.com/v1/
NEBIUS_MODEL=nvidia/nemotron-3-super-120b-a12b
MANO_DATA_MODE=demo
MANO_TIMEZONE=America/Chicago
```

**Do not share or commit API keys.** Optional: `TAVILY_API_KEY` for real resource research.

Verify the real model first (not covered by automated tests; it needs your key and an internet connection):

```bash
python -m scripts.verify_nebius
```

Launch MANO:

```bash
uvicorn server:app --reload
```

Then open **http://localhost:8000**.

For your own everyday use, set `MANO_DATA_MODE=local` in `.env`: everything is kept in one private file (`mano_private.db`) on your computer. Do **not** use `local` mode on a public host.

The original Streamlit version still works with `streamlit run app.py`.

### Deploy (free)

**Render:** push to GitHub, then on render.com choose **New → Blueprint** and pick this repo. `render.yaml` sets everything up; paste `NEBIUS_API_KEY` and `TAVILY_API_KEY` when asked. Free instances sleep when idle, so the first visit can take about a minute.

**Any Docker host** (Hugging Face Spaces, Fly.io, Railway): use the included `Dockerfile` and set the same two keys as secrets.

## Try the end-to-end story

In the web app, **More → Try a sample week** loads the same fictional data; "Your week" holds the radar, "Opportunities" the radar search, and replies show **How I worked this out**. The steps below use the Streamlit labels.

1. Click **Load fictional student week**. It seeds a *fictional* profile (goals and interests), a yesterday conversation about an exam, a club presentation and the gym, plus a conflicting shift and meeting.
2. Check **Your radar**: it should identify the overlap in the time blocks.
3. With a Nebius key configured, click **Yesterday's recap**. The assistant should recall the factual earlier conversation without invented detail.
4. Click **Rescue my week**. MANO should discuss the existing conflict and suggest realistic steps, not invent time availability.
5. Approve a proposed task/time block. Confirm that it's visible in the right-hand panel. The suggestion shouldn't have been saved before approval.
6. Download the calendar `.ics`, **import** it into a calendar, and inspect the alert. A download alone does not create real notifications.
7. Approve an email draft and inspect it under **Prepared email drafts**. It is not sent.
8. With a Tavily key, click **My news briefing**: news on the profile's interests, each item numbered to a real source.
9. Type something like "I'm exhausted and just need to vent". MANO should respond with empathy and propose no tasks.
10. Ask "What should I focus on this week, and are there internships I should apply for?" Open **How MANO worked this out** under the reply to see the skills it chained.
11. Open **Opportunity Radar**, pick Internships, click **Find for me**, then **Track this application** on a card and approve it.

## Reproducible checks

```bash
python -m pip install pytest
python -m pytest -q
python -m scripts.demo_check
```

A public demo should set `MANO_MAX_CALLS_PER_SESSION` and must still be protected with provider spending controls; this is a *per-browser* safety rail, not a global limit.

The automated suite (64 tests) checks the web API (private per-browser data, live agent steps, approval gate, limits), the agent loop and skill budget, skill sandboxing, Opportunity Radar validation, date-specific recall, strict approval, conflict correctness, data deletion, backup/restore, Rescue Studio planning, calendar event generation, email drafts, the goals profile, friend mode and the news briefing's source handling (with the model and search mocked). These are **unit tests**, not a claim that the live model or Streamlit GUI was externally verified.

## Security and privacy boundaries

- **No live Gmail sending, Google Calendar synchronization, LMS integration, SMS push, continuous background reminders, or browser autonomy** in this version. Don't imply otherwise in the pitch.
- `demo` mode isolates each Streamlit session in memory. A new session loses its history.
- `local` mode persists an **unencrypted SQLite database** on one private laptop. This is not suitable for shared/public hosting; do not store sensitive records in a public demonstration.
- User text and selected context are sent to Nebius for inference when the user requests an answer. Avoid entering real IDs, medical data, passwords, or other confidential records in the demo.
- LLM-produced actions are validated and queued for explicit approval, not executed invisibly.
- Source lookup through Tavily is optional, requires a separate key and human approval, and never implies that unsupported web research has occurred.
- A production release would need encrypted multi-tenant identity and storage, complete deletion controls, secure OAuth permissions, background jobs with explicit opt-in, provider rate limits, and more extensive evaluations.

## Roadmap: from MVP to everyday assistant

The vision is one assistant a student can rely on daily. Each step below needs explicit, revocable permission and per-user encrypted storage, which is why none of them is faked in this MVP.

1. **Accounts and persistent memory** on the hosted app (sign-in, encrypted per-user database), replacing manual backup/restore.
2. **Gmail and Google/Outlook Calendar** via OAuth: read deadlines and invites, check real availability in Rescue Studio, send approved drafts.
3. **College systems** (Canvas/Blackboard) for assignments and grades, plus campus resources and opportunities matched to the student's goals.
4. **Proactive check-ins**: an opt-in morning brief and deadline nudges by push or email.
5. **Browsing context**, strictly opt-in, from a browser extension the student controls (for example, saving pages to MANO rather than collecting history).

See [docs/V3_RESCUE_STUDIO_DEMO.md](docs/V3_RESCUE_STUDIO_DEMO.md) for the demo walkthrough.

## Hackathon submission plan

**Submission deadline: Friday October 30, 2026 at 10:00 AM PDT / 12:00 PM CDT.** Official rules: https://nebiusglobalaihackathon.devpost.com/rules

- [ ] Run an actual Nebius inference request and verify consistent structured output (requires personal key)
- [ ] Capture 3–5 realistic but fictional workflows and measure if tasks were extracted correctly
- [ ] Public hosted demo running in `demo` mode, with key configured securely via hosting secrets
- [ ] Publish a public repo with a visible MIT license, reproducible setup instructions, and demo screenshots
- [ ] Submit a working demo URL, public repository URL and under-three-minute public YouTube video
- [ ] Demo one **real** sequence: conflict detected -> AI reasons -> action proposed -> human approves -> task or .ics exported -> prior decision recalled
- [ ] Describe honest limitations; label the prototype as an MVP

### Three-minute demo narrative

- **0:00–0:20:** “An exam, a shift and a club deadline all land in the same week. You shouldn't have to mentally juggle them.”
- **0:20–0:55:** Import fictional scenario, show exact scheduling overlap and deadline radar.
- **0:55–1:45:** Trigger a real Nemotron model response and **Rescue my week**; approve a suggested action.
- **1:45–2:20:** Show an exported calendar item and draft preparation (both need approval).
- **2:20–2:50:** Ask what was discussed yesterday; demonstrate factual recall.
- **2:50–3:00:** One-sentence tech stack and why MANO matters beyond the hackathon.

## Sources

- [NVIDIA / Nebius model docs and Python example](https://nebius.com/services/token-factory/nemotron)
- [Official hackathon rules](https://nebiusglobalaihackathon.devpost.com/rules)
- [Judging criteria explained](https://nebiusglobalaihackathon.devpost.com/updates/46204-here-s-how-judging-works)

## Project files

- `server.py` — FastAPI web app: API, live agent steps over SSE, per-browser private storage, demo limits
- `web/` — chat-first interface (plain HTML, CSS and JavaScript; no build step)
- `app.py` — original Streamlit UI (kept as a fallback)
- `mano_agent.py` — reusable skills registry, Nemotron agent loop, Opportunity Radar
- `mano_core.py` — SQLite storage, goals profile, deterministic radar, Nemotron integration (mentor and friend modes), news briefing, validated proposals, calendar export
- `scripts/demo_check.py` — Offline workflow check
- `scripts/verify_nebius.py` — Optional real-model smoke check
- `tests/` — Automated local tests
- `.env.example` — Local configuration template
- `LICENSE` — MIT

Built as a hackathon prototype. Performance and reliability claims require separate measured evaluation.
