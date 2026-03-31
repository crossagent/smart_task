import httpx
import sqlite3
import json
import os
import time
import uuid

# ===========================================================================
# CONFIGURATION
# ===========================================================================
NOTION_API_KEY = "ntn_b35838965039TTLDAamONPd1vUMvg7S9TueVWXOk8yQaxt"
DB_FILE = "smart_task_app/data/smart_task.db"

# Database IDs (Discovery v2)
DB_IDS = {
    "Task": "32e0d59d-ebb7-8075-89bd-ce186649d3bc",
    "Feature": "32e0d59d-ebb7-8084-b00e-d51d6a372dc7",
    "Initiative": "32e0d59d-ebb7-80a2-95f8-cdd4f6b622b0",
    "Module": "32e0d59d-ebb7-8030-bd39-f9e3b3e60bd8",
    "Resource": "32e0d59d-ebb7-809d-ab88-d088e4d0653f"
}

# ===========================================================================
# HELPERS
# ===========================================================================

def get_prop_text(page, prop_name):
    prop = (page["properties"].get(prop_name) or {}) if "properties" in page else {}
    if not prop: return ""
    p_type = prop.get("type")
    if p_type == "title":
        return "".join([t["plain_text"] for t in prop.get("title", []) or []])
    if p_type == "rich_text":
        return "".join([t["plain_text"] for t in prop.get("rich_text", []) or []])
    if p_type == "status":
        status_data = prop.get("status") or {}
        return status_data.get("name", status_data.get("value", ""))
    if p_type == "select":
        select_data = prop.get("select") or {}
        return select_data.get("name", "")
    if p_type == "number":
        return prop.get("number")
    if p_type == "date":
        date_data = prop.get("date") or {}
        return date_data.get("start", "")
    if p_type == "relation":
        ids = [r["id"] for r in (prop.get("relation") or [])]
        return ids[0] if ids else None
    return ""

def notion_query_all(db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    results = []
    has_more = True
    next_cursor = None
    local_proxy = "http://127.0.0.1:10808"
    
    print(f"  Fetching Notion DB {db_id}...")
    with httpx.Client(proxy=local_proxy, timeout=120.0, verify=False) as client:
        while has_more:
            payload = {"start_cursor": next_cursor} if next_cursor else {}
            try:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                results.extend(data.get("results", []))
                has_more = data.get("has_more", False)
                next_cursor = data.get("next_cursor")
            except Exception as e:
                print(f"  Notion API Error: {e}. Retrying without proxy...")
                try:
                    with httpx.Client(proxy=None, timeout=120.0) as f_client:
                        resp = f_client.post(url, json=payload, headers=headers)
                        resp.raise_for_status()
                        data = resp.json()
                        results.extend(data.get("results", []))
                        has_more = data.get("has_more", False)
                        next_cursor = data.get("next_cursor")
                except Exception as e2:
                    print(f"  Critical Error: {e2}")
                    break
    return results

# ===========================================================================
# MIGRATION
# ===========================================================================

def migrate():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    print("🚀 Starting Notion to SQLite Migration (v10)...")

    # Mapping state: notion_id -> local_sqlite_uuid
    id_map = {}

    # Stage 1: Resources & Modules
    for cat in ["Resource", "Module"]:
        items = notion_query_all(DB_IDS[cat])
        for record in items:
            name = get_prop_text(record, "Name") or get_prop_text(record, "Title")
            if not name: continue
            
            uid = str(uuid.uuid4())
            id_map[record["id"]] = uid
            
            if cat == "Resource":
                cap = get_prop_text(record, "Weekly_Capacity")
                status = get_prop_text(record, "Status") or "Available"
                cursor.execute("REPLACE INTO resources (id, name, weekly_capacity, status, origin_id) VALUES (?, ?, ?, ?, ?)",
                             (uid, name, cap or 40, status, record["id"]))
            else:
                cursor.execute("REPLACE INTO modules (id, name, status, type, origin_id) VALUES (?, ?, ?, ?, ?)",
                             (uid, name, "Active", "Technical", record["id"]))
    conn.commit()

    # Stage 2: Events
    items = notion_query_all(DB_IDS["Initiative"])
    for record in items:
        name = get_prop_text(record, "Name") or get_prop_text(record, "Title")
        if not name: continue
        uid = str(uuid.uuid4())
        id_map[record["id"]] = uid
        status = get_prop_text(record, "Status") or "Planning"
        cursor.execute("REPLACE INTO events (id, name, status, memo_content, origin_id) VALUES (?, ?, ?, ?, ?)",
                     (uid, name, status, name, record["id"]))
    conn.commit()

    # Stage 3: Features
    items = notion_query_all(DB_IDS["Feature"])
    for record in items:
        name = get_prop_text(record, "Name") or get_prop_text(record, "Title")
        if not name: continue
        uid = str(uuid.uuid4())
        id_map[record["id"]] = uid
        
        # Link to Event
        e_id = get_prop_text(record, "Initiative")
        local_e_id = id_map.get(e_id)
        
        # Fuzzy Matching Fallback: If no relation, match by common keywords (e.g. "画质", "分包")
        if not local_e_id:
            keywords = ["画质", "分包", "性能", "包体", "billboard"]
            found_keyword = next((k for k in keywords if k in name), None)
            if found_keyword:
                cursor.execute("SELECT id FROM events WHERE name LIKE ?", (f"%{found_keyword}%",))
                res = cursor.fetchone()
                if res:
                    local_e_id = res[0]
                    print(f"    ✨ Fuzzy-matched Feature '{name}' to Event via keyword '{found_keyword}'")

        cursor.execute("REPLACE INTO features (id, name, event_id, status, origin_id) VALUES (?, ?, ?, ?, ?)",
                     (uid, name, local_e_id, "Active", record["id"]))
    conn.commit()

    # Stage 4: Tasks
    items = notion_query_all(DB_IDS["Task"])
    for record in items:
        name = get_prop_text(record, "Name") or get_prop_text(record, "Title")
        if not name: continue
        uid = str(uuid.uuid4())
        
        # Relational Logic
        e_id = get_prop_text(record, "Initiative")
        f_id = get_prop_text(record, "Feature")
        m_id = get_prop_text(record, "Module")
        r_id = get_prop_text(record, "Resource")
        
        local_e = id_map.get(e_id)
        local_f = id_map.get(f_id)
        local_m = id_map.get(m_id)
        local_r = id_map.get(r_id)
        
        # Link Healing: If direct Event link is missing, inherit from Feature
        if not local_e and local_f:
            cursor.execute("SELECT event_id FROM features WHERE id = ?", (local_f,))
            res = cursor.fetchone()
            if res and res[0]:
                local_e = res[0]
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS features 
                         (id TEXT PRIMARY KEY, name TEXT, event_id TEXT, owner TEXT, collaborators TEXT, status TEXT, origin_id TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS tasks 
                         (id TEXT PRIMARY KEY, name TEXT, event_id TEXT, feature_id TEXT, module_id TEXT, resource_id TEXT, status TEXT, estimated_hours REAL, origin_id TEXT)''')
        
        est = get_prop_text(record, "Estimated_Hours") or 0
        status = get_prop_text(record, "Status") or "Todo"
        
        cursor.execute("""
            REPLACE INTO tasks (id, name, event_id, feature_id, module_id, resource_id, objective, estimated_hours, status, origin_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, name, local_e, local_f, local_m, local_r, name, est, status, record["id"]))
    
    conn.commit()
    conn.close()
    print("✅ Migration to SQLite Finished Successfully!")

if __name__ == "__main__":
    migrate()
