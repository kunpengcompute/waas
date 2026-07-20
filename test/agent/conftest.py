import os
import sys


AGENT_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../src/agent")
)
if AGENT_SRC not in sys.path:
    sys.path.insert(0, AGENT_SRC)
