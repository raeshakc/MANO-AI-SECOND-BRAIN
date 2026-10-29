# MANO — Your AI Second Brain for Student Life

> **Submission text draft. Edit after live verification.** Do not claim live deployment, real API calls, user feedback, or measured outcomes until they have been tested.

**Tagline:** Make room for life. MANO connects commitments, remembers context, and helps students turn overwhelming weeks into approved next steps.

## Inspiration

Students rarely struggle with just one deadline. Classes, shifts, clubs, interviews, exercise, and relationships compete for the same limited time. Most productivity tools track individual tasks but don't help students reason about how those commitments interact. We set out to build a companion that turns a messy conversation into an actionable, user-controlled plan.

## What it does

MANO is a student-centered Personal AI agent. Students can explain what's happening in their lives conversationally. MANO considers saved commitments, earlier conversations and an objective schedule-conflict detector to provide context-aware help. It proposes tasks, study blocks, and email drafts for approval. It can export calendar events as `.ics` files. Its fictional student-week demo shows an exam, club deadline and overlapping work shift and meeting.

## How we built it

We built a Python/Streamlit application with SQLite task and conversation storage, deterministic overlap analysis, a proposal-validation and approval layer, and NVIDIA Nemotron 3 Super served through the Nebius Token Factory OpenAI-compatible inference API. The key model call is in `mano_core.py` (`ask_nemotron`); the interface and approvals live in `app.py`. All proposals are checked against defined action types, and no draft is sent or task saved without user approval. Optional Tavily integration offers approved source-grounded research when separately configured.

## Challenges

A personal assistant is only useful when it doesn't invent deadlines, claim it completed unsupported actions, or silently change a user's schedule. We separated deterministic facts (saved tasks, overlap windows, dates) from the model's conversational reasoning, validated proposal shapes, and kept actions behind explicit approval. We also designed a fictional public demo that avoids collecting real private student data.

## What we learned

A useful second-brain assistant needs more than memory retrieval. It needs reliable context, tool boundaries, an understandable approval flow and accurate descriptions of what actually happened. The strongest experience is connecting a person's commitments while keeping them in control.

## Next steps

Add opt-in integrations for calendars and learning platforms, robust authenticated private storage, background reminders, reusable planning skills, and systematic evaluation with consenting student testers. These are **future plans**, not MVP features.

## Built with

NVIDIA Nemotron 3 Super · Nebius Token Factory · Python · Streamlit · SQLite · OpenAI-compatible API · Optional Tavily API

## Links (complete before submission)

- **Live demo:** [ADD VERIFIED URL]
- **GitHub:** [ADD VERIFIED URL]
- **YouTube demo:** [ADD PUBLIC URL UNDER 3 MINUTES]

## Required provider feedback (write after testing)

- Onboarding time from API key to first successful inference: [MEASURE]
- What worked well with Token Factory/Nemotron: [OBSERVED]
- One specific improvement you would suggest: [OBSERVED]
- Would you use it again, and why: [PERSONAL EXPERIENCE]
