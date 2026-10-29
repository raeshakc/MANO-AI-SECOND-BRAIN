"""Optional real-inference check. Requires NEBIUS_API_KEY and internet."""
import os
from dotenv import load_dotenv
from mano_core import ask_nemotron, connect

load_dotenv()

if not os.getenv("NEBIUS_API_KEY"):
    raise SystemExit("No NEBIUS_API_KEY found. Add it to your own .env first.")

reply, actions = ask_nemotron(connect(), "Say hello in one sentence. Do not propose any task.")
print("LIVE NVIDIA/Nebius model reply:", reply)
print("Proposed actions:", actions)
