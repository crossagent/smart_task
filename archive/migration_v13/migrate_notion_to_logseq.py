import httpx
import json
import os
import time

# ===========================================================================
# NOTION CONFIGURATION
# ===========================================================================
NOTION_API_KEY = "ntn_b35838965039TTLDAamONPd1vUMvg7S9TueVWXOk8yQaxt"

# 数据库 ID (经 Discovery v2 修正)
DB_IDS = {
    "Task": "32e0d59d-ebb7-8075-89bd-ce186649d3bc",
    "Feature": "32e0d59d-ebb7-8084-b00e-d51d6a372dc7",
    "Initiative": "32e0d59d-ebb7-80a2-95f8-cdd4f6b622b0",
    "Module": "32e0d59d-ebb7-8030-bd39-f9e3b3e60bd8",
    "Resource": "32e0d59d-ebb7-809d-ab88-d088e4d0653f"
}

# ===========================================================================
# LOGSEQ CONFIGURATION
# ===========================================================================
LOGSEQ_API_URL = "http://localhost:12315/api"
LOGSEQ_API_TOKEN = "gogozhou" 

# ===========================================================================
# MAPPING STATE
# ===========================================================================
# { notion_page_id: { "uuid": "xxx", "page": "[[Name]]" } }
id_map = {}

def logseq_call(method, *args):
    """Call Logseq Local HTTP API."""
    headers = {"Authorization": f"Bearer {LOGSEQ_API_TOKEN}"}
    payload = {"method": method, "args": list(args)}
    try:
        with httpx.Client(proxy=None, timeout=30.0) as client:
            resp = client.post(LOGSEQ_API_URL, json=payload, headers=headers)
            return resp.json()
    except Exception as e:
        print(f"Logseq API Error ({method}): {e}")
        return None

def notion_query_all(db_id):
    """Fetch all records from a Notion database."""
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
                print(f"    Fetched {len(results)} items so far...")
            except Exception as e:
                print(f"  Notion API Error: {e}. Retrying without proxy...")
                try:
                    with httpx.Client(proxy=None, timeout=120.0) as fallback_client:
                        resp = fallback_client.post(url, json=payload, headers=headers)
                        resp.raise_for_status()
                        data = resp.json()
                        results.extend(data.get("results", []))
                        has_more = data.get("has_more", False)
                        next_cursor = data.get("next_cursor")
                except Exception as e2:
                    print(f"  Critical Error: {e2}")
                    break
    return results

def get_prop_text(page, prop_name):
    """Extract plain text from Notion property."""
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
        return [r["id"] for r in (prop.get("relation") or [])]
    return ""

def ensure_page(name):
    """Ensure a page exists and return its UUID."""
    page = logseq_call("logseq.Editor.createPage", name, {}, {"redirect": False})
    if page and "uuid" in page:
        return page["uuid"]
    page = logseq_call("logseq.Editor.getPage", name)
    if page and "uuid" in page:
        return page["uuid"]
    return None

async def migrate():
    print("🚀 Starting Logseq 5-Entity Migration (v9 - Visibility Enhanced)...")
    
    # --- STAGE 1: Resources & Modules ---
    print("\n--- Stage 1: Migrating Resources & Modules ---")
    for category in ["Resource", "Module"]:
        notion_items = notion_query_all(DB_IDS[category])
        for item in notion_items:
            name = get_prop_text(item, "Name") or get_prop_text(item, "Title")
            if not name: continue
            
            p_name = f"{category}/{name}"
            print(f"Migrating {category}: {name}")
            page_uuid = ensure_page(p_name)
            if page_uuid:
                ret = logseq_call("logseq.Editor.insertBlock", page_uuid, f"[[{category}]] {name}", {})
                if ret and "uuid" in ret:
                    b_uuid = ret.get("uuid")
                    id_map[item["id"]] = {"uuid": b_uuid, "page": f"[[{p_name}]]"}
                    logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "class", f"[[{category}]]")
                    logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "origin-id", item["id"])
                    
                    if category == "Resource":
                        cap = get_prop_text(item, "Weekly_Capacity")
                        logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "weekly-capacity", str(cap or 40))
                        logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "status", "[[Available]]")
                    elif category == "Module":
                        logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "knowledge-base", "")
                        logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "status", "[[Active]]")

    # --- STAGE 2: Events ---
    print("\n--- Stage 2: Migrating Events (备忘/事件表) ---")
    notion_events = notion_query_all(DB_IDS["Initiative"])
    for item in notion_events:
        name = get_prop_text(item, "Name") or get_prop_text(item, "Title")
        if not name: continue
        
        p_name = f"Event/{name[:50]}"
        print(f"Migrating Event: {name}")
        page_uuid = ensure_page(p_name)
        if page_uuid:
            ret = logseq_call("logseq.Editor.insertBlock", page_uuid, name, {})
            if ret and "uuid" in ret:
                b_uuid = ret.get("uuid")
                id_map[item["id"]] = {"uuid": b_uuid, "page": f"[[{p_name}]]"}
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "class", "[[Event]]")
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "status", f"[[{get_prop_text(item, 'Status') or 'Planning'}]]")
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "origin-id", item["id"])

    # --- STAGE 3: Features ---
    print("\n--- Stage 3: Migrating Features (业务特性) ---")
    notion_features = notion_query_all(DB_IDS["Feature"])
    for item in notion_features:
        name = get_prop_text(item, "Name") or get_prop_text(item, "Title")
        if not name: continue
        
        p_name = f"Feature/{name[:50]}"
        print(f"Migrating Feature: {name}")
        page_uuid = ensure_page(p_name)
        if page_uuid:
            ret = logseq_call("logseq.Editor.insertBlock", page_uuid, name, {})
            if ret and "uuid" in ret:
                b_uuid = ret.get("uuid")
                id_map[item["id"]] = {"uuid": b_uuid, "page": f"[[{p_name}]]"}
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "class", "[[Feature]]")
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "status", "[[Active]]")
                logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "origin-id", item["id"])
                
                # Relate to Event
                i_ids = get_prop_text(item, "Initiative")
                i_id = i_ids[0] if isinstance(i_ids, list) and i_ids else i_ids
                if i_id and i_id in id_map:
                    # Link to both Page and Block for visibility in Linked References
                    link_val = f"{id_map[i_id]['page']} (({id_map[i_id]['uuid']}))"
                    logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "event", link_val)

    # --- STAGE 4: Tasks ---
    print("\n--- Stage 4: Migrating Tasks (最小执行粒子) ---")
    tasks_page_uuid = ensure_page("Tasks")
    notion_tasks = notion_query_all(DB_IDS["Task"])
    for item in notion_tasks:
        name = get_prop_text(item, "Name") or get_prop_text(item, "Title")
        if not name: continue
        print(f"Migrating Task: {name}")
        ret = logseq_call("logseq.Editor.insertBlock", tasks_page_uuid, name, {})
        if ret and "uuid" in ret:
            b_uuid = ret.get("uuid")
            logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "class", "[[Task]]")
            logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "objective", name)
            logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "origin-id", item["id"])
            
            for prop, target in [("Module", "module"), ("Resource", "resource"), ("Feature", "feature"), ("Initiative", "event")]:
                target_ids = get_prop_text(item, prop)
                t_id = target_ids[0] if isinstance(target_ids, list) and target_ids else target_ids
                if t_id and t_id in id_map:
                    link_val = f"{id_map[t_id]['page']} (({id_map[t_id]['uuid']}))"
                    logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, target, link_val)
            
            est = get_prop_text(item, "Estimated_Hours")
            logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "estimated-hours", str(est or 0))
            status = get_prop_text(item, "Status")
            logseq_call("logseq.Editor.upsertBlockProperty", b_uuid, "status", f"[[{status or 'Todo'}]]")

    print("\n✅ Migration (v9) Finished Successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(migrate())
