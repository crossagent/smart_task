import httpx
import os
import time

LOGSEQ_API_TOKEN = "gogozhou"
LOGSEQ_API_URL = "http://localhost:12315/api"

def logseq_call(method, *args):
    headers = {"Authorization": f"Bearer {LOGSEQ_API_TOKEN}"}
    payload = {"method": method, "args": list(args)}
    try:
        r = httpx.post(LOGSEQ_API_URL, json=payload, headers=headers, timeout=30)
        return r.json()
    except Exception as e:
        print(f"  ❌ Logseq Action Failed ({method}): {e}")
        return None

def main():
    print("🧹 Cleaning up Logseq 5-Entity Namespaces...")

    # Get all pages
    pages = logseq_call("logseq.Editor.getAllPages")
    if not pages:
        print("Logseq is empty or unreachable.")
        return

    # Namespaces to wipe (case-insensitive)
    targets = ["event/", "initiative/", "feature/", "resource/", "module/", "tasks"]
    
    deleted_count = 0
    for page in pages:
        name = page["name"].lower()
        should_delete = any(name.startswith(t) for t in targets) or name in ["tasks", "event", "feature", "resource", "module"]
        
        if should_delete:
            print(f"  🗑️ Deleting Page: {page['name']}")
            logseq_call("logseq.Editor.deletePage", page["name"])
            deleted_count += 1
            time.sleep(0.05) # Rate limiting

    # Also clear any blocks on major pages just in case
    for p in ["Tasks", "Event", "Feature", "Resource", "Module"]:
        logseq_call("logseq.Editor.deletePage", p)

    print(f"\n✅ Cleanup Complete! Deleted {deleted_count} pages.")
    print("Graph is now clean for v9 migration.")

if __name__ == "__main__":
    main()
