import httpx
import json
import os
import time

# ===========================================================================
# NOTION CONFIGURATION (ONE-TIME ONLY)
# ===========================================================================
NOTION_API_KEY = "YOUR_NOTION_API_KEY_HERE"  # 请在此填入你的 Notion Token

# 数据库 ID 自动提取自之前的配置
DB_IDS = {
    "Task": "32e0d59d-ebb7-8044-93e9-000ba6f9ab3d",
    "Feature": "32e0d59d-ebb7-8001-8bd0-000b1fd12363",
    "Initiative": "32e0d59d-ebb7-80c7-88a1-000b493dcc61",
    "Module": "32e0d59d-ebb7-80e7-8f18-000b37afcab4",
    "Resource": "32e0d59d-ebb7-8070-a498-000b7430b8b1"
}

# ===========================================================================
# LOGSEQ CONFIGURATION
# ===========================================================================
LOGSEQ_API_URL = "http://localhost:12315/api"
LOGSEQ_API_TOKEN = "YOUR_LOGSEQ_API_TOKEN_HERE" # 请在此填入你的 Logseq API Token

# ===========================================================================
# MAPPING STATE
# ===========================================================================
# { notion_page_id: logseq_block_uuid }
id_map = {}

def logseq_call(method, *args):
    """Call Logseq Local HTTP API."""
    headers = {"Authorization": f"Bearer {LOGSEQ_API_TOKEN}"}
    payload = {"method": method, "args": list(args)}
    try:
        resp = httpx.post(LOGSEQ_API_URL, json=payload, headers=headers, timeout=30.0)
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
    
    while has_more:
        payload = {"start_cursor": next_cursor} if next_cursor else {}
        resp = httpx.post(url, json=payload, headers=headers)
        data = resp.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")
    
    return results

def get_prop_text(page, prop_name):
    """Extract plain text from Notion property."""
    prop = page["properties"].get(prop_name, {})
    p_type = prop.get("type")
    if p_type == "title":
        return "".join([t["plain_text"] for t in prop.get("title", [])])
    if p_type == "rich_text":
        return "".join([t["plain_text"] for t in prop.get("rich_text", [])])
    if p_type == "status":
        return prop.get("status", {}).get("name", "")
    if p_type == "select":
        return prop.get("select", {}).get("name", "")
    if p_type == "number":
        return prop.get("number")
    if p_type == "relation":
        return [r["id"] for r in prop.get("relation", [])]
    return ""

# ===========================================================================
# MIGRATION STAGES
# ===========================================================================

async def migrate():
    print("🚀 Starting Notion to Logseq Migration...")
    
    # --- STAGE 1: Resources & Modules ---
    print("\n--- Stage 1: Migrating Resources & Modules ---")
    for category in ["Resource", "Module"]:
        notion_items = notion_query_all(DB_IDS[category])
        for item in notion_items:
            name = get_prop_text(item, "Name")
            print(f"Migrating {category}: {name}")
            
            # Create Page/Block in Logseq
            parent = f"{category}/{name}"
            # Use logseq.Editor.createBlock (here we simplify, creating a page would be better but createBlock with parent_page works)
            ret = logseq_call("logseq.Editor.createBlock", parent, f"[[{category}]] {name}", {}, {"isPageBlock": True})
            if ret:
                uuid = ret.get("uuid")
                id_map[item["id"]] = uuid
                # Set properties
                logseq_call("logseq.Editor.upsertBlockProperty", uuid, "class", f"[[{category}]]")
                if category == "Resource":
                    cap = get_prop_text(item, "Weekly_Capacity")
                    logseq_call("logseq.Editor.upsertBlockProperty", uuid, "weekly-capacity", str(cap or 40))

    # --- STAGE 2: Initiatives ---
    print("\n--- Stage 2: Migrating Initiatives ---")
    notion_initiatives = notion_query_all(DB_IDS["Initiative"])
    for item in notion_initiatives:
        name = get_prop_text(item, "Name")
        print(f"Migrating Initiative: {name}")
        ret = logseq_call("logseq.Editor.createBlock", f"Initiative/{name[:30]}", name, {}, {"isPageBlock": True})
        if ret:
            uuid = ret.get("uuid")
            id_map[item["id"]] = uuid
            logseq_call("logseq.Editor.upsertBlockProperty", uuid, "class", "[[Initiative]]")
            logseq_call("logseq.Editor.upsertBlockProperty", uuid, "status", f"[[{get_prop_text(item, 'Status')}]]")

    # --- STAGE 3: Features ---
    print("\n--- Stage 3: Migrating Features ---")
    notion_features = notion_query_all(DB_IDS["Feature"])
    for item in notion_features:
        name = get_prop_text(item, "Name")
        print(f"Migrating Feature: {name}")
        ret = logseq_call("logseq.Editor.createBlock", f"Feature/{name[:30]}", name, {}, {"isPageBlock": True})
        if ret:
            uuid = ret.get("uuid")
            id_map[item["id"]] = uuid
            logseq_call("logseq.Editor.upsertBlockProperty", uuid, "class", "[[Feature]]")
            # Relate to Initiative
            initiative_ids = get_prop_text(item, "Initiative")
            if initiative_ids and initiative_ids[0] in id_map:
                logseq_call("logseq.Editor.upsertBlockProperty", uuid, "initiative", f"(({id_map[initiative_ids[0]]}))")

    # --- STAGE 4: Tasks ---
    print("\n--- Stage 4: Migrating Tasks ---")
    notion_tasks = notion_query_all(DB_IDS["Task"])
    for item in notion_tasks:
        name = get_prop_text(item, "Name")
        print(f"Migrating Task: {name}")
        ret = logseq_call("logseq.Editor.createBlock", "Tasks", name, {}, {"isPageBlock": False}) # Append to a Tasks page
        if ret:
            uuid = ret.get("uuid")
            id_map[item["id"]] = uuid
            logseq_call("logseq.Editor.upsertBlockProperty", uuid, "class", "[[Task]]")
            
            # Map Properties
            for prop, target in [("Module", "module"), ("Resource", "resource"), ("Feature", "feature"), ("Initiative", "initiative")]:
                target_ids = get_prop_text(item, prop)
                if isinstance(target_ids, list) and target_ids and target_ids[0] in id_map:
                    logseq_call("logseq.Editor.upsertBlockProperty", uuid, target, f"(({id_map[target_ids[0]]}))")
            
            est = get_prop_text(item, "Estimated_Hours")
            logseq_call("logseq.Editor.upsertBlockProperty", uuid, "estimated-hours", str(est or 0))
            status = get_prop_text(item, "Status")
            logseq_call("logseq.Editor.upsertBlockProperty", uuid, "status", f"[[{status or 'Todo'}]]")

    print("\n✅ Migration Finished Successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(migrate())
