import httpx
import sqlite3
import json
import time

# ===========================================================================
# LOGSEQ CONFIGURATION
# ===========================================================================
LOGSEQ_API_URL = "http://localhost:12315/api"
LOGSEQ_API_TOKEN = "gogozhou" 
DB_FILE = "smart_task_app/data/smart_task.db"

# ===========================================================================
# HELPERS
# ===========================================================================

def logseq_call(method, *args):
    headers = {"Authorization": f"Bearer {LOGSEQ_API_TOKEN}"}
    payload = {"method": method, "args": list(args)}
    try:
        with httpx.Client(proxy=None, timeout=30.0) as client:
            resp = client.post(LOGSEQ_API_URL, json=payload, headers=headers)
            return resp.json()
    except Exception as e:
        print(f"Logseq API Error ({method}): {e}")
        return None

def ensure_page(name):
    page = logseq_call("logseq.Editor.createPage", name, {}, {"redirect": False})
    if page and "uuid" in page:
        return page["uuid"]
    page = logseq_call("logseq.Editor.getPage", name)
    if page and "uuid" in page:
        return page["uuid"]
    return None

# ===========================================================================
# SYNC LOGIC (v13: Multi-call Property Sync)
# ===========================================================================

def sync():
    print("🔄 Starting SQLite -> Logseq Synchronization (v13 - Multi-call Mode)...")
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    id_to_logseq = {}

    # Stage 1: Resources & Modules
    print("\n📦 Stage 1: Syncing Resources & Modules")
    category_map = {"resources": "Resource", "modules": "Module"}
    for table, category in category_map.items():
        data = cursor.execute(f"SELECT * FROM {table}").fetchall()
        for i, row in enumerate(data):
            p_name = f"{category}/{row['name']}"
            print(f"  [{category} {i+1}/{len(data)}] {row['name']}")
            page_uuid = ensure_page(p_name)
            if page_uuid:
                ret = logseq_call("logseq.Editor.insertBlock", page_uuid, row['name'], {})
                if ret and "uuid" in ret:
                    b_uuid = ret.get("uuid")
                    id_to_logseq[row["id"]] = {"uuid": b_uuid, "page": f"[[{p_name}]]"}
                    logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "class", f"[[{category}]]")
                    logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "origin-id", row["origin_id"])
                    
                    if category == "Resource":
                        logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "weekly-capacity", str(row["weekly_capacity"] or 40))
                        logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "status", f"[[{row['status']}]]")
                    elif category == "Module":
                        logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "status", f"[[{row['status']}]]")

    # Stage 2: Events
    print("\n📅 Stage 2: Syncing Events")
    events = cursor.execute("SELECT * FROM events").fetchall()
    for i, row in enumerate(events):
        p_name = f"Event/{row['name'][:50]}"
        print(f"  [Event {i+1}/{len(events)}] {row['name']}")
        page_uuid = ensure_page(p_name)
        if page_uuid:
            ret = logseq_call("logseq.Editor.insertBlock", page_uuid, row["name"], {})
            if ret and "uuid" in ret:
                b_uuid = ret.get("uuid")
                id_to_logseq[row["id"]] = {"uuid": b_uuid, "page": f"[[{p_name}]]"}
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "class", "[[Event]]")
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "status", f"[[{row['status'] or 'Planning'}]]")
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "origin-id", row["origin_id"])

    # Stage 3: Features
    print("\n✨ Stage 3: Syncing Features")
    features = cursor.execute("SELECT * FROM features").fetchall()
    for i, row in enumerate(features):
        p_name = f"Feature/{row['name'][:50]}"
        print(f"  [Feature {i+1}/{len(features)}] {row['name']}")
        page_uuid = ensure_page(p_name)
        if page_uuid:
            ret = logseq_call("logseq.Editor.insertBlock", page_uuid, row["name"], {})
            if ret and "uuid" in ret:
                b_uuid = ret.get("uuid")
                id_to_logseq[row["id"]] = {"uuid": b_uuid, "page": f"[[{p_name}]]"}
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "class", "[[Feature]]")
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "status", f"[[{row['status']}]]")
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "origin-id", row["origin_id"])
                
                if row.get("owner"):
                    logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "owner", row["owner"])
                if row.get("collaborators"):
                    logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "collaborators", row["collaborators"])
                
                if row["event_id"] in id_to_logseq:
                    target = id_to_logseq[row["event_id"]]
                    logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "event", target['page'])

    # Stage 4: Tasks
    print("\n🚀 Stage 4: Syncing Tasks...")
    tasks_page_uuid = ensure_page("Tasks")
    tasks = cursor.execute("SELECT * FROM tasks").fetchall()
    for i, row in enumerate(tasks):
        print(f"  [Task {i+1}/{len(tasks)}] {row['name']}")
        ret = logseq_call("logseq.Editor.insertBlock", tasks_page_uuid, row["name"], {})
        if ret and "uuid" in ret:
            b_uuid = ret.get("uuid")
            logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "class", "[[Task]]")
            logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "objective", row["name"])
            logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "origin-id", row["origin_id"])
            logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "estimated-hours", str(row["estimated_hours"] or 0))
            logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "status", f"[[{row['status'] or 'Todo'}]]")
            
            for field, col in [("event", "event_id"), ("feature", "feature_id"), ("module", "module_id"), ("resource", "resource_id")]:
                if row[col] in id_to_logseq:
                    target = id_to_logseq[row[col]]
                    logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, field, target['page'])

    conn.close()
    print("\n✅ Synchronization Complete!")

if __name__ == "__main__":
    sync()
