"""The agent loop with a stand-in LLM: tools run in Python, bad tool calls don't crash it."""
import json
import types

import pytest

from app.services import agent as agent_mod


def _call(i, name, args):
    return types.SimpleNamespace(id=f"c{i}", type="function", function=types.SimpleNamespace(name=name, arguments=args))


def _msg(content=None, calls=None):
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content, tool_calls=calls))])


@pytest.fixture
def fake_llm(monkeypatch):
    seen = []
    script = [
        _msg(calls=[_call(1, "cash_forecast", '{"target_date": "2026-11-13"}'), _call(2, "customer_profile", "{broken json")]),
        _msg(calls=[_call(3, "what_if", json.dumps({"changes": [{"type": "delay_customer", "customer": "Mehta", "days": 15}]}))]),
        _msg(content="Answer: Likely short on 13 Nov."),
    ]

    def create(**kw):
        seen.append(kw)
        return script.pop(0)

    fake = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
    monkeypatch.setattr(agent_mod, "llm", lambda: fake)
    return seen


def test_agent_runs_tools_and_answers(client, demo, fake_llm):
    r = client.post("/api/ask", headers=demo, json={"question": "Can I pay Vertex on Friday?", "memory": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"].startswith("Answer:")
    assert [c["tool"] for c in body["tool_calls"]] == ["cash_forecast", "customer_profile", "what_if"]

    tool_msgs = [m for m in fake_llm[-1]["messages"] if m["role"] == "tool"]
    forecast_result = json.loads(tool_msgs[0]["content"])
    assert forecast_result["scenarios"]["likely"]["balance_on_target"] == -194008   # real numbers from Python
    assert "error" in json.loads(tool_msgs[1]["content"])                            # broken args reported back
    assert "comparison" in json.loads(tool_msgs[2]["content"])

    t = client.get("/api/timeline", headers=demo).json()
    assert t["items"][0]["type"] == "recommendation" and t["items"][0]["live"]


def test_baseline_agent_has_no_memory_tools(client, demo, fake_llm):
    fake_llm.clear()
    client.post("/api/ask", headers=demo, json={"question": "Can I pay Vertex on Friday?", "memory": False})
    names = [t["function"]["name"] for t in fake_llm[0]["tools"]]
    assert names == ["cash_forecast", "upcoming_bills"]
