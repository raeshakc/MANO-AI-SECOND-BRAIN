import json
import sys
import types
from mano_core import ask_nemotron, connect


def fake_model(monkeypatch, reply):
    calls = []
    class FakeCompletions:
        def create(self, **kw):
            calls.append(kw)
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=reply))])
    class FakeOpenAI:
        def __init__(self, **kw):
            self.chat = types.SimpleNamespace(completions=FakeCompletions())
    monkeypatch.setenv('NEBIUS_API_KEY', 'not-a-real-key')
    monkeypatch.setitem(sys.modules, 'openai', types.SimpleNamespace(OpenAI=FakeOpenAI))
    return calls


def test_no_false_success_when_model_forgets_action(monkeypatch):
    calls = fake_model(monkeypatch, json.dumps({'reply': "Sure! I've created the task.", 'proposals': []}))
    reply, proposals = ask_nemotron(connect(), 'Please create a task called "Study" tomorrow at 6 PM')
    assert 'nothing was saved' in reply.lower()
    assert proposals == []
    assert calls[0]['response_format'] == {'type': 'json_object'}


def test_proposal_requires_approval_and_is_valid(monkeypatch):
    fake_model(monkeypatch, json.dumps({'reply': "I've created the task", 'proposals': [
        {'kind': 'add_task', 'title': 'Study Computer Architecture', 'due_at': '2026-10-30T18:00', 'category': 'academic'}
    ]}))
    reply, proposals = ask_nemotron(connect(), 'Please create a task called "Study Computer Architecture" for Oct 30 at 6 PM')
    assert len(proposals) == 1
    assert proposals[0]['due_at'] == '2026-10-30T18:00'
    assert 'nothing has been saved' in reply.lower()


def test_normal_conversation_not_overridden(monkeypatch):
    fake_model(monkeypatch, json.dumps({'reply':'Happy to help you plan your day.', 'proposals':[]}))
    reply, proposals = ask_nemotron(connect(), 'How are you today?')
    assert reply == 'Happy to help you plan your day.'
    assert proposals == []
