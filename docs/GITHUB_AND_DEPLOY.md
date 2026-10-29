# Publish MANO: GitHub → live demo → Devpost

Submission deadline: **Friday, October 30, 2026, 10:00 AM PDT / noon CDT**.

## 1. Run locally (Mac)

Use a Python 3.11–3.13 installation. Extract the ZIP and open Terminal **inside this project directory**.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt pytest
cp .env.example .env
python -m pytest -q
```

Sign up for Nebius Token Factory, create a key, add `NEBIUS_API_KEY=...` to `.env` locally and **never share it**.

```bash
python -m scripts.verify_nebius
streamlit run app.py
```

Verify one actual AI reply and one approved task. A green offline test result is not evidence that the NVIDIA/Nebius API was used.

## 2. Publish to GitHub

Connect GitHub in ChatGPT if you want help publishing directly. Alternatively, create a **new empty public** GitHub repo named `MANO-AI-Second-Brain` without auto-initializing it, then run the following **inside this project directory**:

```bash
git init
git branch -M main
git add .
git status --short
git diff --cached --name-only
git commit -m "Build MANO student AI agent MVP"
git remote add origin https://github.com/YOUR-USERNAME/MANO-AI-Second-Brain.git
git push -u origin main
```

Before committing, check that `.env`, `*.db`, and `.streamlit/secrets.toml` are **not** staged. Use your actual GitHub username. GitHub may ask you to authenticate via browser or the GitHub CLI. **Do not paste a token into the repository.**

## 3. Deploy Streamlit Community Cloud

1. Open https://share.streamlit.io/ and choose **Create app** → **I have an app**.
2. Select your GitHub repository, `main` branch and `app.py` entrypoint.
3. In **Advanced settings → Secrets**, add this TOML with your real private key, without putting it in GitHub:

```toml
NEBIUS_API_KEY = "YOUR_PRIVATE_KEY"
NEBIUS_BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/"
NEBIUS_MODEL = "nvidia/nemotron-3-super-120b-a12b"
MANO_DATA_MODE = "demo"
MANO_TIMEZONE = "America/Chicago"
MANO_MAX_CALLS_PER_SESSION = "10"
```

4. Deploy, test the public `*.streamlit.app` link in a private/incognito window. Test a real Nemotron response and ensure session memory doesn't leak to a different browser session.
5. Share the demo URL with judges; make sure the app remains usable during the judging period. **Check Nebius credits and rate limits**: a per-browser session limit is not a global spend cap. Consider further abuse protection if the link is shared widely.

## 4. Submit on Devpost

- Join: https://nebiusglobalaihackathon.devpost.com/
- Project: `MANO — Your AI Second Brain for Student Life`
- Track: **Personal AI**
- Provide the public GitHub repo, live demo, and public YouTube link under 3 minutes.
- Use `docs/DEVPOST_DRAFT.md` as a starting point, but edit descriptions to match the features you personally verified in the live app.
- Explain how NVIDIA Nemotron inference through Nebius Token Factory powers the actual responses.
- Answer the required Nebius/NVIDIA feedback questions based on your real experience.
- Save a draft early and **submit** before the deadline; saving a draft alone isn't the final submission.

## Required honesty and safety

MANO currently **does not** send emails, automatically sync calendars, access a school's LMS, perform periodic background checking, or deliver push notifications. Its `.ics` is a downloadable reminder file and must be imported. The public demo uses ephemeral session memory; persistent memory is available only in private local mode, not a secure user-account production service. Do not claim otherwise.
