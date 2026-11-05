import os
from dotenv import load_dotenv
load_dotenv()
from groq import Groq
from hindsight_client import Hindsight

g = Groq().chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": "Say hi"}],
)
print("Groq OK:", g.choices[0].message.content)

h = Hindsight(
    base_url=os.getenv("HINDSIGHT_URL"),
    api_key=os.getenv("HINDSIGHT_API_KEY"),
)
h.retain(bank_id="test", content="Customer A usually pays 10 days late")
print("Hindsight OK:", h.recall(bank_id="test", query="How does Customer A pay?"))