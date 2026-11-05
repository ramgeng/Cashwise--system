"""Talk to the agent from the terminal.

Run from the project root:
    python -m scripts.ask                       # chat with memory
    python -m scripts.ask --baseline            # the "before" agent: no memory, naive forecast
    python -m scripts.ask "Can I pay Vertex on Friday?"

Commands inside the chat:
    /feedback <text>   tell the agent what you liked or didn't (saved to memory)
    /outcome <text>    record what actually happened (saved to memory)
    /quit
"""
import argparse

from app.agent import CashAgent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("question", nargs="*")
    p.add_argument("--baseline", action="store_true", help="no memory, invoices assumed paid on due date")
    p.add_argument("--verbose", action="store_true", help="show tool calls")
    a = p.parse_args()

    agent = CashAgent(use_memory=not a.baseline, verbose=a.verbose)
    mode = "BASELINE (no memory)" if a.baseline else "WITH MEMORY"
    print(f"CashFlow Intelligence - {mode} - today is {agent.today}\n")
    try:
        if a.question:
            print(agent.ask(" ".join(a.question))["answer"])
            return
        while True:
            q = input("\nYou: ").strip()
            if not q:
                continue
            if q in ("/quit", "/exit"):
                break
            if q.startswith("/feedback "):
                agent.feedback(q[len("/feedback "):])
                print("Saved. I'll use that next time.")
                continue
            if q.startswith("/outcome "):
                agent.outcome(q[len("/outcome "):])
                print("Outcome saved.")
                continue
            res = agent.ask(q)
            if a.verbose and res["memories_used"]:
                print(f"  ({len(res['memories_used'])} memories used)")
            print("\nAgent:\n" + res["answer"])
    finally:
        agent.close()


if __name__ == "__main__":
    main()
