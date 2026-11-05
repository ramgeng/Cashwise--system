"""Talk to the agent in the terminal.

    python -m scripts.ask                       # chat as the demo business, with memory
    python -m scripts.ask --baseline            # no memory, invoices assumed paid on time
    python -m scripts.ask "Can I pay Vertex on Friday?"
Inside the chat:  /feedback <text>   /outcome <text>   /quit
"""
from app.core.errors import AppError
from app.services.agent import CashAgent
from scripts._pick import context, parser, pick


def main():
    p = parser(__doc__)
    p.add_argument("question", nargs="*")
    p.add_argument("--baseline", action="store_true")
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args()
    b = pick(a.business)
    books, fc, mem = context(b)
    agent = CashAgent(fc, None if a.baseline else mem, b, use_memory=not a.baseline, verbose=a.verbose)
    print(f"Cashwise - {b['name']} - {'no memory' if a.baseline else 'with memory'} - today is {books.as_of_date()}\n")

    def answer(q):
        try:
            print("\nAgent:\n" + agent.ask(q)["answer"])
        except AppError as e:
            print(f"\n{e.detail}")

    if a.question:
        return answer(" ".join(a.question))
    while True:
        q = input("\nYou: ").strip()
        if q in ("/quit", "/exit"):
            break
        if q.startswith("/feedback "):
            agent.feedback(q[10:]); print("Saved.")
        elif q.startswith("/outcome "):
            agent.outcome(q[9:]); print("Saved.")
        elif q:
            answer(q)


if __name__ == "__main__":
    main()
