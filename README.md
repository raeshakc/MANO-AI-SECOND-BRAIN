# MANO ✦ — More life, less mental load

**NVIDIA × Nebius Global AI Hackathon (2026) · Personal AI track**

MANO is a student-focused life-coordination agent: an assistant that understands conversations and commitments in context, identifies genuine deadline or schedule conflicts, proposes a realistic way forward, and turns recommendations into **approved** tasks, time blocks, email drafts, or source-grounded research.

> **Pitch:** Most apps help you track one part of your life. MANO connects them. When study, work, friendships and career goals collide, MANO helps you decide what matters and take the next step.

## What works in this MVP

| Capability | Implementation | Requires API? |
|---|---|---|
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

## Important limits and privacy

- Public `demo` mode keeps data in a private in-memory database **only for the current browser session**. Reloading or leaving may lose this data. It does not automatically remember across visits. A visitor can download a MANO JSON backup and later manually restore it; this is not automatic sync.
- `local` mode preserves SQLite memory between sessions on a **trusted personal computer**. Do not switch public hosting to `local`: without authentication it could expose one person's records to another.
- The Rescue Studio checks **only** times saved inside MANO and the user-selected planning window. It cannot see Google/Apple Calendar, travel time, work changes, or actual outside availability. Review all proposed times before approval.
- Task/calendar actions are local to MANO until you approve them. Calendar exports require a separate import. MANO does **not** send push notifications, emails, or silently change external calendars.
- Public model calls can use the owner's Nebius credit balance; the per-session request cap is not global usage protection.

## Technical design

```text
Student -> Streamlit chat -> local context assembly
                                  |— dated conversation history / topic retrieval
                                  |— assignments + deadlines (SQLite)
                                  |— scheduled blocks + deterministic conflict radar
                             NVIDIA Nemotron 3 Super
                             via Nebius Token Factory
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
streamlit run app.py
```

To keep conversation data **between restarts on your own computer**, set `MANO_DATA_MODE=local` before launching. The default `demo` mode keeps each browser session's data in its own memory database, which does **not** persist across new browser sessions. Do **not** enable `local` mode on a public multi-user host.

## Try the end-to-end story

1. Click **Load fictional student week**. It seeds a *fictional* yesterday conversation about an exam, a club presentation and the gym, plus a conflicting shift and meeting.
2. Check **Your radar**: it should identify the overlap in the time blocks.
3. With a Nebius key configured, click **Yesterday's recap**. The assistant should recall the factual earlier conversation without invented detail.
4. Click **Rescue my week**. MANO should discuss the existing conflict and suggest realistic steps, not invent time availability.
5. Approve a proposed task/time block. Confirm that it's visible in the right-hand panel. The suggestion shouldn't have been saved before approval.
6. Download the calendar `.ics`, **import** it into a calendar, and inspect the alert. A download alone does not create real notifications.
7. Approve an email draft and inspect it under **Prepared email drafts**. It is not sent.

## Reproducible checks

```bash
python -m pip install pytest
python -m pytest -q
python -m scripts.demo_check
```

A public demo should set `MANO_MAX_CALLS_PER_SESSION` and must still be protected with provider spending controls; this is a *per-browser* safety rail, not a global limit.

The automated suite checks persistence, date-specific recall, strict approval, conflict correctness, data deletion, calendar event generation, email drafts and prompt construction. These are **unit tests**, not a claim that the live model or Streamlit GUI was externally verified.

## Security and privacy boundaries

- **No live Gmail sending, Google Calendar synchronization, LMS integration, SMS push, continuous background reminders, or browser autonomy** in this version. Don't imply otherwise in the pitch.
- `demo` mode isolates each Streamlit session in memory. A new session loses its history.
- `local` mode persists an **unencrypted SQLite database** on one private laptop. This is not suitable for shared/public hosting; do not store sensitive records in a public demonstration.
- User text and selected context are sent to Nebius for inference when the user requests an answer. Avoid entering real IDs, medical data, passwords, or other confidential records in the demo.
- LLM-produced actions are validated and queued for explicit approval, not executed invisibly.
- Source lookup through Tavily is optional, requires a separate key and human approval, and never implies that unsupported web research has occurred.
- A production release would need encrypted multi-tenant identity and storage, complete deletion controls, secure OAuth permissions, background jobs with explicit opt-in, provider rate limits, and more extensive evaluations.

## Publish and submit

See **[GitHub → deployment → Devpost instructions](docs/GITHUB_AND_DEPLOY.md)**, **[Devpost text draft](docs/DEVPOST_DRAFT.md)**, **[video script](docs/VIDEO_SCRIPT.md)** and **[verification log](docs/TEST_RESULTS.md)**.

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

- `app.py` — Streamlit UI and approvals
- `mano_core.py` — SQLite storage, deterministic radar, Nemotron integration, validated proposals, calendar export
- `scripts/demo_check.py` — Offline workflow check
- `scripts/verify_nebius.py` — Optional real-model smoke check
- `tests/` — Automated local tests
- `.env.example` — Local configuration template
- `LICENSE` — MIT

Built as a hackathon prototype. Performance and reliability claims require separate measured evaluation.
