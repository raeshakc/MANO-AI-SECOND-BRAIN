# MANO V3 — Rescue Studio demonstration and release checklist

## What changed
- A **deadline-first Rescue Studio** that reads saved commitments, respects time blocks that exist inside MANO, uses the student's selected daily availability window, suggests concrete tentative focus sessions, and shows why it chose them. All calendar writes require review and approval.
- Duplicate task and time-block proposals are no longer repeatedly staged when the same item is already pending or saved.
- A **manual private-memory vault**: export your session to JSON, then restore it in a later session. It is user-controlled portability, not background synchronization or an automatic long-term memory service.

## Local installation of this incremental patch
1. In VS Code, stop Streamlit (Ctrl+C).
2. Replace `mano_core.py` and `app.py` in the existing repository with the two files from the V3 patch ZIP. Do not replace `.env` or any secrets.
3. Copy the new `test_rescue_studio.py` and `test_portable_memory.py` into `tests/`.
4. Run `python -m pytest -q` (expected: 41 passed).
5. Run `python -m streamlit run app.py`.
6. Test the Rescue Studio with fictional data before pushing.
7. Verify `git status --short`, `git check-ignore -v .env`, and `git ls-files .env .venv`, then `git add app.py mano_core.py tests/ README.md docs/` and `git commit -m "Add deadline-aware Rescue Studio and portable memory"` and `git push origin main`.
8. Streamlit Cloud normally pulls latest main automatically. Verify the public app and credentials and monitor logs.

## Real product-demo sequence (roughly 2 minutes)
1. Start with an empty temporary demo session. Click **Load fictional student week**.
2. Show the three parts of life MANO knows: upcoming school deadline, club presentation, and schedule overlap (work shift vs. club meeting). These are **fictional** seeded data.
3. Open **Rescue Studio**. Select a genuine availability window; click **Build my rescue plan**. Point out that MANO schedules around its **saved** meetings and prioritizes the earlier deadline.
4. Click **Stage these blocks for my approval**. Check **Ready when you are** and approve just one. Show it now appears under saved time blocks. Do not claim it was added to an external calendar.
5. Ask Nemotron: “What's most urgent this week, and how can I protect time for my long-term software engineering goal?” Explain that the context and action proposals use the actual NVIDIA model through Nebius.
6. Download the MANO JSON vault. Open a fresh browser session and restore it (using the uploaded file and checkbox); ask MANO about prior commitments. Explain this is **manual portability**, whereas local single-user mode saves SQLite data across restarts.
7. End with the public app and GitHub link and acknowledge current scope honestly.

## Before Devpost submission
- Re-test the public deployed version, not only localhost.
- Record a public YouTube demo under 3 minutes, based on actual live interactions.
- Confirm no API keys or personal data were committed, and no genuine secrets are visible in screenshots/videos.
- State that calendar files need import and that memory is automatic on a personal local installation but manual backup/restore in the unauthenticated hosted demo.
- Make sure the repo's README and license are public and the model runtime call is working.
