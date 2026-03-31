import httpx
import json
import time

LOGSEQ_API_URL = "http://localhost:12315/api"
LOGSEQ_API_TOKEN = "gogozhou"

def logseq_call(method, *args):
    headers = {"Authorization": f"Bearer {LOGSEQ_API_TOKEN}"}
    payload = {"method": method, "args": list(args)}
    with httpx.Client(proxy=None, timeout=60.0) as client:
        try:
            resp = client.post(LOGSEQ_API_URL, json=payload, headers=headers)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

def batch_audit():
    print("🚀 Starting Final Governance Audit for 71 Tasks (SoT Mode)...")
    
    # 1. 直接拉取 Tasks 页面的 Block Tree (这是最稳健的 SoT 路径)
    tree = logseq_call("logseq.Editor.getPageBlocksTree", "Tasks")
    
    if not tree:
        print("❌ Error: Could not fetch 'Tasks' page blocks.")
        return

    total = len(tree)
    print(f"✅ Found {total} Task nodes. Commencing review...")

    audit_report = []
    
    for block in tree:
        content = block.get("content", "")
        # Check both standard properties dictionary and the raw content text
        props = block.get("properties", {})
        
        issues = []
        
        # Governance Markers: look in props OR look for 'key::' in text
        has_event = "event" in props or "event::" in content.lower()
        has_module = "module" in props or "module::" in content.lower()
        has_resource = "resource" in props or "resource::" in content.lower()
        
        if not has_event: issues.append("❌ 缺需求")
        if not has_module: issues.append("❌ 缺物理模块")
        if not has_resource: issues.append("❌ 缺执行人")
        
        status = "HEALTHY" if not issues else "BROKEN"
        issue_str = " | ".join(issues) if issues else "治理结构 100% 完整"
        core_title = content.split("\n")[0]
        audit_report.append(f"[{status}] Task: {core_title} | {issue_str}")
            
    print("\n" + "="*60)
    print("📋 SMART TASK 最终验收报告 (Logseq 原生)")
    print("="*60)
    for line in audit_report:
        print(line)
    print("="*60)
    print(f"验收完成。总数: {total} | 状态: {'全部合规' if 'BROKEN' not in str(audit_report) else '仍有漏洞'}")
            
    print("\n" + "="*50)
    print("📋 SMART TASK 治理体检报告 (Logseq 原生)")
    print("="*50)
    for line in audit_report:
        print(line)
    print("="*50)
    print(f"Audit Complete. Total Scanned: {total}")

if __name__ == "__main__":
    batch_audit()
