
import sys
import traceback
from google.adk.plugins.base_plugin import BasePlugin

def find_subclasses(cls):
    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in find_subclasses(c)]
    )

print("--- Starting ADK Plugin Discovery ---")
try:
    # Import relevant modules to trigger registration
    import google.adk.plugins.logging_plugin
    try:
        import google.adk.a2a.plugins
    except ImportError:
        pass
    
    # List all subclasses of BasePlugin
    all_plugins = find_subclasses(BasePlugin)
    print(f"Found {len(all_plugins)} plugin classes:")
    for p in all_plugins:
        print(f" - {p.__module__}.{p.__name__}")

    # Check specifically for A2aLogPlugin
    try:
        from google.adk.a2a.plugins import A2aLogPlugin
        print("\n[SUCCESS] A2aLogPlugin is available!")
    except ImportError:
        print("\n[INFO] A2aLogPlugin not found in google.adk.a2a.plugins")

except Exception as e:
    print(f"\n[ERROR] Discovery failed: {e}")
    traceback.print_exc()
