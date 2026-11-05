"""The CashFlow Intelligence agent loop.

For every question:
  1. recall   - pull relevant memories from Hindsight (behaviour, past decisions, preferences)
  2. reason   - Groq LLM decides which deterministic tools to call
  3. compute  - Python tools return forecasts / what-ifs (the LLM never does the maths)
  4. explain  - LLM answers with evidence, patterns, assumptions and uncertainty
  5. retain   - the recommendation is stored, so outcomes and feedback can be compared later

use_memory=False gives the "before" agent for the demo: naive due-date forecast, no memory.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime

import groq

from app import forecast as fc
from app.config import BANK_ID, BUSINESS_NAME, GROQ_API_KEY
from app.memory import get_client, recall
from app.tools import BASELINE_TOOLS, MEMORY_TOOLS, run_tool, tool_cash_forecast

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_STEPS = 6

RULES = """You are CashFlow Intelligence, the cash-flow assistant for {business}, a consumer-electronics
distributor in Kochi run by its owner Anil. Today is {today}.

Hard rules:
- NEVER calculate, add up or estimate money yourself. Every number you state must come from a tool
  result. Prefer the pre-formatted *_text fields (e.g. "Rs 1.94 L").
- Expected collections are not guaranteed cash. Always say which scenario (best / likely / worst) a
  number belongs to.
- You give cash-flow insights and options; the owner decides. Do not present this as professional
  financial or legal advice.
{memory_rules}
Answer format (plain text, short, phone-friendly):
Answer: one or two sentences with the key number and date.
Recommended actions: up to 3 numbered, specific actions (who, what, by when).
Evidence: invoice / bill ids and history counts the numbers rest on.
{pattern_line}Assumptions & uncertainty: the range (worst to best) and the main assumptions.
"""

MEMORY_RULES = """- Use the memories below and the recall_memory tool to personalise advice: how each customer
  responds to reminders or calls, which suppliers allowed extensions, past crunches, and the owner's
  preferences. Never recommend something the owner has rejected before; say why if relevant.
- Use customer_profile before recommending which customer to chase.
- Use what_if to show the effect of the actions you recommend."""

BASELINE_RULES = """- You have no history or memory: treat every invoice as paid on its due date."""


class CashAgent:
    def __init__(self, use_memory: bool = True, model: str = MODEL, verbose: bool = False):
        if not GROQ_API_KEY:
            raise SystemExit("GROQ_API_KEY is missing from .env")
        self.llm = groq.Groq(api_key=GROQ_API_KEY)
        self.model = model
        self.use_memory = use_memory
        self.verbose = verbose
        self.mem = get_client() if use_memory else None
        self.today = fc.as_of_date()
        self.history: list[dict] = []   # conversation so far (user/assistant only)

    # ------------------------------------------------------------ memory
    def _prefetch_memories(self, question: str) -> list[str]:
        if not self.mem:
            return []
        seen, out = set(), []
        for q in (question, "owner preferences, decisions and feedback about cash, loans, rent and suppliers"):
            try:
                for m in recall(self.mem, q)[:6]:
                    if m not in seen:
                        seen.add(m)
                        out.append(m)
            except Exception as e:
                print(f"  (memory recall failed: {str(e)[:80]})")
        return out[:10]

    def _retain(self, content: str, tags: list[str], context: str):
        if not self.mem:
            return
        try:
            self.mem.retain(bank_id=BANK_ID, content=content, context=context, tags=tags,
                            timestamp=datetime.combine(self.today, datetime.now().time()).isoformat() + "Z",
                            document_id=f"{tags[0]}-{uuid.uuid4().hex[:10]}", retain_async=True)
        except Exception as e:
            print(f"  (could not save to memory: {str(e)[:80]})")

    def feedback(self, text: str):
        """Owner corrects or rates advice, e.g. 'Don't suggest asking Vertex for extensions'."""
        self._retain(f"On {self.today} the owner gave feedback on the agent's advice: {text}. "
                     "Follow this in future recommendations.", ["owner_feedback", "owner:OWNER"],
                     "owner feedback")

    def outcome(self, text: str):
        """What actually happened, e.g. 'Called Mehta, INV-1179 paid on 9 Nov'."""
        self._retain(f"On {self.today} the owner reported an outcome: {text}", ["outcome"],
                     "actual outcome of a recommendation")

    # ------------------------------------------------------------ LLM loop
    def _system_prompt(self, memories: list[str]) -> str:
        p = RULES.format(business=BUSINESS_NAME, today=self.today.isoformat(),
                         memory_rules=MEMORY_RULES if self.use_memory else BASELINE_RULES,
                         pattern_line="Pattern from memory: what history says about the people involved.\n"
                         if self.use_memory else "")
        if memories:
            p += "\nRelevant memories (from Hindsight):\n" + "\n".join(f"- {m}" for m in memories)
        return p

    def _chat(self, messages, tools, attempt=0):
        try:
            return self.llm.chat.completions.create(
                model=self.model, messages=messages, tools=tools, tool_choice="auto",
                temperature=0.2 if attempt == 0 else 0.0, max_completion_tokens=1800)
        except groq.RateLimitError:
            if attempt >= 3:
                raise
            time.sleep(3 * (attempt + 1))
            return self._chat(messages, tools, attempt + 1)
        except groq.BadRequestError as e:
            # Open models sometimes emit malformed tool calls ("tool_use_failed"). Retry, then degrade.
            if attempt >= 2:
                raise
            if self.verbose:
                print(f"  (tool call failed, retrying: {str(e)[:100]})")
            messages = messages + [{"role": "system", "content":
                                    "Your last tool call was malformed. Call one tool at a time with valid JSON arguments."}]
            return self._chat(messages, tools, attempt + 1)

    def ask(self, question: str) -> dict:
        memories = self._prefetch_memories(question)
        tools = MEMORY_TOOLS if self.use_memory else BASELINE_TOOLS
        messages = [{"role": "system", "content": self._system_prompt(memories)}] + self.history[-6:] + \
                   [{"role": "user", "content": question}]
        calls = []
        answer = None
        for _ in range(MAX_STEPS):
            try:
                resp = self._chat(messages, tools)
            except groq.BadRequestError:
                answer = self._fallback(question, memories)
                break
            msg = resp.choices[0].message
            if not msg.tool_calls:
                answer = msg.content
                break
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    result = run_tool(tc.function.name, args, self.mem, self.use_memory)
                except Exception as e:  # bad arguments, unknown names: tell the model, let it fix
                    args, result = {}, {"error": str(e)}
                calls.append({"tool": tc.function.name, "args": args})
                if self.verbose:
                    print(f"  -> {tc.function.name}({json.dumps(args)[:120]})")
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(result, default=str)[:14000]})
        if answer is None:
            answer = self._fallback(question, memories)

        self.history += [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
        if self.use_memory:
            self._retain(f"On {self.today} the owner asked: \"{question}\". The agent recommended: {answer[:900]}",
                         ["recommendation"], "agent recommendation and prediction")
        return {"answer": answer, "tool_calls": calls, "memories_used": memories}

    def _fallback(self, question, memories):
        """If tool calling keeps failing, compute the forecast ourselves and ask for a plain answer."""
        data = tool_cash_forecast(21, None, use_history=self.use_memory)
        resp = self.llm.chat.completions.create(
            model=self.model, temperature=0.0, max_completion_tokens=1500,
            messages=[{"role": "system", "content": self._system_prompt(memories)},
                      {"role": "user", "content": f"{question}\n\nForecast tool result:\n"
                                                  f"{json.dumps(data, default=str)[:12000]}"}])
        return resp.choices[0].message.content

    def close(self):
        if self.mem:
            self.mem.close()
