"""Talking to the agent, and teaching it: feedback, outcomes, memory search."""
from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import datetime
from threading import Lock

from fastapi import APIRouter, Depends

from app.core.errors import AppError
from app.db import tenant
from app.routes.deps import BusinessContext, current_business
from app.schemas import AskIn, FeedbackIn, OutcomeIn
from app.services.agent import CashAgent

router = APIRouter(prefix="/api", tags=["agent"])
log = logging.getLogger("cashwise.agent")

# One agent per (user, business, memory mode) keeps each person's chat history; oldest dropped first.
_agents: OrderedDict = OrderedDict()
_lock = Lock()
MAX_AGENTS = 100


def _agent(ctx: BusinessContext, memory: bool) -> CashAgent:
    key = (ctx.user["id"], ctx.id, memory)
    with _lock:
        if key in _agents:
            _agents.move_to_end(key)
            agent = _agents[key]
        else:
            agent = CashAgent(ctx.forecaster, ctx.memory if memory else None, ctx.business, use_memory=memory)
            _agents[key] = agent
            while len(_agents) > MAX_AGENTS:
                _agents.popitem(last=False)
    agent.fc = ctx.forecaster          # fresh view of the books for every request
    agent.tools.fc, agent.tools.b = ctx.forecaster, ctx.books
    return agent


def _log(ctx: BusinessContext, kind: str, text: str) -> None:
    with ctx.books.engine.begin() as c:
        c.execute(tenant.agent_log.insert().values(
            created_at=f"{ctx.books.as_of_date().isoformat()}T{datetime.now():%H:%M}", user_id=ctx.user["id"],
            kind=kind, text=text[:2000]))


@router.post("/ask")
def ask(body: AskIn, ctx: BusinessContext = Depends(current_business)):
    question = body.question.strip()
    if not question:
        raise AppError(422, "Type a question first.", "empty_question")
    try:
        res = _agent(ctx, body.memory).ask(question)
    except AppError:
        raise
    except Exception as e:
        log.exception("agent failed")
        raise AppError(502, f"The agent couldn't answer this time: {str(e)[:160]}", "agent_failed")
    if body.memory:
        _log(ctx, "recommendation", f"Asked: {question}\n{(res['answer'] or '')[:600]}")
    return res


@router.post("/feedback")
def feedback(body: FeedbackIn, ctx: BusinessContext = Depends(current_business)):
    verdict = "" if body.helpful is None else ("The owner found this advice useful. " if body.helpful
                                              else "The owner rejected this advice. ")
    about = f'About the question "{body.question}": ' if body.question else ""
    text = (about + verdict + body.text).strip()
    if not text:
        raise AppError(422, "Nothing to save.", "empty_feedback")
    _agent(ctx, True).feedback(text)
    _log(ctx, "feedback", (verdict + body.text).strip() or text)
    return {"saved": True}


@router.post("/outcome")
def outcome(body: OutcomeIn, ctx: BusinessContext = Depends(current_business)):
    text = body.text.strip()
    _agent(ctx, True).outcome(text)
    _log(ctx, "outcome", text)
    return {"saved": True}


@router.get("/memories")
def memories(q: str = "important patterns, decisions and preferences for this business",
             ctx: BusinessContext = Depends(current_business)):
    try:
        return {"query": q, "memories": ctx.memory.recall(q[:500])[:12]}
    except AppError:
        raise
    except Exception as e:
        raise AppError(502, f"Memory search failed: {str(e)[:160]}", "memory_failed")
