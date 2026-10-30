"""The web app's API, with Nemotron and Tavily replaced by scripted stand-ins."""
import json

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import mano_core as core  # noqa: E402
import server  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "MODE", "demo")
    monkeypatch.setattr(server, "SESSION_DIR", tmp_path)
    monkeypatch.setattr(server, "PER_SESSION_PER_DAY", 15)
    monkeypatch.setattr(server, "_global_usage", {})
    monkeypatch.setenv("NEBIUS_API_KEY", "test")
    monkeypatch.setenv("TAVILY_API_KEY", "test")

    def no_network(*a, **k):
        raise RuntimeError("tests must not call the real model")
    monkeypatch.setattr(core, "_nemotron_json", no_network)
    return TestClient(server.app)


def script(monkeypatch, *responses):
    calls = []

    def fake(messages, **kwargs):
        calls.append(messages)
        r = responses[min(len(calls), len(responses)) - 1]
        return json.dumps(r), r

    monkeypatch.setattr(core, "_nemotron_json", fake)
    return calls


def events(response):
    out = []
    for chunk in response.text.strip().split("\n\n"):
        name = chunk.split("\n")[0].removeprefix("event: ")
        out.append((name, json.loads(chunk.split("\n")[1].removeprefix("data: "))))
    return out


def test_first_visit_gets_cookie_and_warm_greeting(client):
    r = client.get("/api/state")
    assert r.status_code == 200 and "mano_sid" in r.cookies
    assert r.json()["greeting"]["headline"] == "Hey there, I'm MANO."
    assert r.json()["onboarding"] == "name"
    client.put("/api/profile", json={"name": "Raesha", "unknown": "x"})
    assert client.get("/api/state").json()["greeting"]["headline"] == "Hey Raesha, what's going on?"


def test_each_browser_has_its_own_private_data(client, tmp_path):
    client.get("/api/state")
    client.post("/api/tasks", json={"title": "Mine", "due_at": None})
    other = TestClient(server.app)
    assert other.get("/api/state").json()["tasks"] == []
    assert [t["title"] for t in client.get("/api/state").json()["tasks"]] == ["Mine"]


def test_forged_cookie_cannot_escape_session_folder(client, tmp_path):
    client.cookies.set("mano_sid", "../../etc/passwd")
    client.get("/api/state")
    assert all(p.parent == tmp_path for p in tmp_path.iterdir())


def known(client):
    client.put("/api/profile", json={"name": "Raesha"})


def test_chat_streams_live_steps_then_saves_reply_steps_and_proposals(client, monkeypatch):
    known(client)
    client.post("/api/tasks", json={"title": "Buildathon", "due_at": "2026-10-31T23:59"})
    script(monkeypatch,
           {"thought": "See what's due", "skill": "check_schedule", "args": {}},
           {"reply": "Here's your plan.", "proposals": [{"kind": "add_task", "title": "Watch DSA video", "due_at": None}]})
    r = client.post("/api/chat", json={"text": "I'm overwhelmed, can you help me prioritize?"})
    names = [n for n, _ in events(r)]
    assert names == ["skill_start", "skill_done", "done"]
    state = events(r)[-1][1]["state"]
    assert state["messages"][-1]["content"] == "Here's your plan."
    assert state["messages"][-1]["steps"][0]["skill"] == "check_schedule"
    assert [p["payload"]["title"] for p in state["proposals"]] == ["Watch DSA video"]
    assert len(state["tasks"]) == 1  # nothing added until approved
    pid = state["proposals"][0]["id"]
    after = client.post(f"/api/proposals/{pid}/approve").json()["state"]
    assert {t["title"] for t in after["tasks"]} == {"Buildathon", "Watch DSA video"}
    assert client.post(f"/api/proposals/{pid}/approve").status_code == 404


def test_listen_mode_never_runs_skills_or_stages_actions(client, monkeypatch):
    known(client)
    calls = script(monkeypatch, {"reply": "I'm here.", "proposals": [{"kind": "add_task", "title": "x"}]})
    r = client.post("/api/chat", json={"text": "Plan my week", "listen": True})
    assert [n for n, _ in events(r)] == ["done"]
    assert events(r)[-1][1]["state"]["proposals"] == []
    assert "FRIEND MODE IS ON" in calls[0][0]["content"]


def test_model_failure_is_reported_not_faked(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("Nemotron returned an empty answer")
    monkeypatch.setattr(core, "_nemotron_json", boom)
    known(client)
    r = client.post("/api/chat", json={"text": "hello"})
    name, data = events(r)[-1]
    assert name == "error" and "empty answer" in data["message"]


def test_demo_limit_per_browser(client, monkeypatch):
    monkeypatch.setattr(server, "PER_SESSION_PER_DAY", 1)
    known(client)
    script(monkeypatch, {"reply": "Hi", "proposals": []})
    assert client.post("/api/chat", json={"text": "one"}).status_code == 200
    second = client.post("/api/chat", json={"text": "two"})
    assert second.status_code == 429 and "today's AI requests" in second.json()["detail"]


def test_chat_needs_the_ai_key(client, monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY")
    known(client)
    assert client.post("/api/chat", json={"text": "hi"}).status_code == 503


def test_tracking_an_opportunity_is_validated_and_needs_approval(client):
    client.get("/api/state")
    assert client.post("/api/opportunities/track", json={"item": {"title": "x", "url": "javascript:alert(1)"}}).status_code == 400
    r = client.post("/api/opportunities/track", json={"item": {"title": "Acme Intern", "url": "https://acme.example/1",
                                                                "deadline": "2026-11-20"}}).json()
    assert r["added"] and r["state"]["tasks"] == []
    assert r["state"]["proposals"][0]["payload"]["due_at"] == "2026-11-20T23:59"


def test_export_import_fresh_chat_and_erase(client):
    client.get("/api/state")
    client.put("/api/profile", json={"name": "Raesha"})
    client.post("/api/tasks", json={"title": "Essay", "due_at": "2026-11-02T17:00"})
    backup = client.get("/api/export").content
    client.post("/api/erase")
    assert client.get("/api/state").json()["profile"]["name"] == ""
    restored = client.post("/api/import", content=backup, headers={"Content-Type": "application/json"}).json()
    assert restored["state"]["profile"]["name"] == "Raesha" and len(restored["state"]["tasks"]) == 1
    assert client.post("/api/import", content=b"not json").status_code == 400
    after = client.post("/api/fresh-chat").json()
    assert after["profile"]["name"] == "Raesha" and after["messages"] == []


def test_bad_task_date_is_explained(client):
    r = client.post("/api/tasks", json={"title": "Essay", "due_at": "next friday"})
    assert r.status_code == 400 and "2026-10-31T18:00" in r.json()["detail"]


def test_home_page_and_calendar(client):
    assert "MANO" in client.get("/").text
    client.post("/api/tasks", json={"title": "Essay", "due_at": "2026-11-02T17:00"})
    ics = client.get("/api/calendar.ics")
    assert ics.headers["content-type"].startswith("text/calendar") and "SUMMARY:Essay" in ics.text






def test_telling_mano_your_name_anytime_is_remembered(client, monkeypatch):
    client.put("/api/profile", json={"name": "You"})  # e.g. a bad earlier guess
    script(monkeypatch, {"reply": "Got it, Raesha!", "proposals": []})
    state = events(client.post("/api/chat", json={"text": "my name is Raesha"}))[-1][1]["state"]
    assert state["profile"]["name"] == "Raesha"
    assert state["greeting"]["headline"] == "Hey Raesha, what's going on?"
    assert core.stated_name("I'm so tired today") == ""  # feelings aren't names


def test_first_meeting_is_a_real_conversation_that_learns_quietly(client, monkeypatch):
    seen = []

    def fake(messages, **kwargs):
        seen.append(messages)
        return "", [
            {"reply": "Lovely to meet you, Raesha. What's been on your mind lately?", "profile_updates": {"name": "Raesha"}},
            {"reply": "You're very welcome!", "profile_updates": {}},
            {"reply": "Twenty-one credits and leading a club is a lot. You're not alone in feeling stretched.",
             "profile_updates": {"school": "CS, 21 credits", "goals": "FAANG job; CompTIA Security+",
                                 "stressors": "feeling stretched", "name": "You", "bogus": "x"}},
        ][len(seen) - 1]

    monkeypatch.setattr(core, "_nemotron_json", fake)
    say = lambda text: events(client.post("/api/chat", json={"text": text}))[-1][1]["state"]
    state = say("HI. MY NAME IS RAESHA")
    assert state["messages"][0]["content"] == core.FIRST_HELLO
    assert state["profile"]["name"] == "Raesha" and state["onboarding"] == "done"
    assert "Not known yet: what they're working toward" in seen[0][0]["content"]
    state = say("THANK YOU NICE TO MEET YOU TOO")
    assert state["profile"]["goals"] == ""  # small talk is not saved as a goal
    state = say("I'm a CS student with 21 credits... I feel stretched")
    assert state["profile"]["goals"] == "FAANG job; CompTIA Security+" and state["profile"]["name"] == "Raesha"
    prompt = core.build_prompt(core.connect(str(next(server.SESSION_DIR.iterdir()))), "next")[0]["content"]
    assert "Not known yet: what they'd like updates on" in prompt  # goals and stressors are known now
    assert "If they ask what you can do" in seen[0][0]["content"]


def test_asking_for_help_overrides_just_listen(client, monkeypatch):
    known(client)
    calls = script(monkeypatch, {"reply": "Here's a plan.", "proposals": []})
    events(client.post("/api/chat", json={"text": "Can you help me plan my week?", "listen": True}))
    assert "FRIEND MODE IS ON" not in calls[0][0]["content"]


def test_mano_talks_like_an_honest_friend(client, monkeypatch):
    known(client)
    calls = script(monkeypatch, {"reply": "Okay, real talk: you've mentioned scrolling three times. That's the Buildathon's biggest enemy.",
                                 "proposals": []})
    events(client.post("/api/chat", json={"text": "I keep scrolling instead of working"}))
    system = calls[0][0]["content"]
    assert "close friend and mentor, not a chatbot" in system and "Tells the truth" in system
    assert 'Never open with stock lines like "I hear you"' in system


def test_cheer_up_song_gets_a_play_link_built_by_mano(client, monkeypatch):
    known(client)
    client.put("/api/profile", json={"music": "Taylor Swift, Coldplay"})
    calls = script(monkeypatch, {"reply": "Here's one to lift you up.", "proposals": [],
                                 "song": {"title": "Fix You", "artist": "Coldplay"}})
    state = events(client.post("/api/chat", json={"text": "I'm sad today", "listen": True}))[-1][1]["state"]
    last = state["messages"][-1]["content"]
    assert "**Fix You by Coldplay**" in last
    assert "https://www.youtube.com/results?search_query=Fix+You+Coldplay" in last
    assert "Taylor Swift, Coldplay" in calls[0][1]["content"]  # MANO knows what you love


def test_friend_check_in_remembers_and_is_cached(client, monkeypatch):
    assert client.get("/api/checkin").json()["text"] is None  # new person: MANO asks their name instead
    known(client)
    calls = script(monkeypatch, {"reply": "Hey you! Did you get a start on the Buildathon last night?"})
    first = client.get("/api/checkin").json()["text"]
    assert first.startswith("Hey you! Did you get a start")
    assert client.get("/api/checkin").json()["text"] == first and len(calls) == 1  # cached until something changes
    assert "Write MANO's first message right now" in calls[0][0]["content"]


def test_motivation_while_listening_retries_instead_of_losing_words(client, monkeypatch):
    known(client)
    calls = script(monkeypatch, {"reply": ""}, {"response": "You founded a club and carry 21 credits. You're not behind."})
    state = events(client.post("/api/chat", json={"text": "I need motivation, I feel like everyone is ahead of me"}))[-1][1]["state"]
    assert state["messages"][-1]["content"].startswith("You founded a club") and len(calls) == 2
    assert "give real encouragement grounded in their story" in calls[0][0]["content"]
