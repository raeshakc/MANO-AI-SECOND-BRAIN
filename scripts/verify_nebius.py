"""Optional real-inference check. Requires NEBIUS_API_KEY and internet."""
import os
from dotenv import load_dotenv

load_dotenv()

from mano_agent import run_agent
from mano_core import ask_nemotron, connect, load_demo_scenario

if not os.getenv("NEBIUS_API_KEY"):
    raise SystemExit("No NEBIUS_API_KEY found. Add it to your own .env first.")

reply, actions = ask_nemotron(connect(), "Say hello in one sentence. Do not propose any task.")
print("LIVE NVIDIA/Nebius model reply:", reply)
print("Proposed actions:", actions)

conn = connect()
load_demo_scenario(conn)
reply, actions, steps = run_agent(conn, "What should I focus on this week? Check my schedule first.")
print("\nAGENT steps:")
for step in steps:
    print(f"  - {step['skill']} {step['args']} -> {step['summary']}")
print("AGENT reply:", reply)
print("AGENT proposals (not saved):", actions)
if not steps:
    print("NOTE: the model answered without using a skill. Try the question again or check the prompt.")
