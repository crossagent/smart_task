
from google.adk.tools import ToolContext
print(f"ToolContext: {ToolContext}")
print(f"Type: {type(ToolContext)}")
print(f"Module: {ToolContext.__module__}")

try:
    from google.adk.agents.invocation_context import InvocationContext
    print(f"InvocationContext: {InvocationContext}")
except ImportError as e:
    print(f"InvocationContext Import Error: {e}")
