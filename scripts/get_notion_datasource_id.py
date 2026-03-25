"""
获取Notion数据库的Data Source ID

用法:
    python scripts/get_notion_datasource_id.py <database_id>

示例:
    python scripts/get_notion_datasource_id.py 1990d59debb781c58d78c302dffea2b5
"""
import asyncio
import os
import sys
import json
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

try:
    from mcp import stdio_client, ClientSession, StdioServerParameters
except ImportError:
    print("错误: 未找到 'mcp' 模块")
    sys.exit(1)

async def find_data_source_id(database_id: str):
    """
    通过database_id查找对应的data_source_id
    
    原理:
    1. 使用API-post-search获取所有可访问的对象
    2. 查找parent中包含目标database_id的项目
    3. 从parent对象中提取data_source_id
    """
    # 移除database_id中的横线（如果有）
    database_id = database_id.replace("-", "")
    
    token = os.environ.get("NOTION_TOKEN") or os.environ.get("NOTION_API_KEY")
    if not token:
        print("错误: 未设置 NOTION_TOKEN 或 NOTION_API_KEY 环境变量")
        return None

    server_params = StdioServerParameters(
        command="npx.cmd" if sys.platform == 'win32' else "npx",
        args=["-y", "@notionhq/notion-mcp-server"],
        env={**os.environ, "NOTION_TOKEN": token}
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                print(f"正在搜索 database_id: {database_id} 的子项目...")
                
                # 搜索所有对象
                result = await session.call_tool(
                    name="API-post-search",
                    arguments={
                        "page_size": 100,
                        "sort": {"direction": "descending", "timestamp": "last_edited_time"}
                    }
                )
                
                if hasattr(result, 'content') and result.content:
                    data = json.loads(result.content[0].text)
                    results = data.get("results", [])
                    
                    # 查找parent包含目标database_id的项目
                    found_data_source_id = None
                    for item in results:
                        parent = item.get('parent', {})
                        parent_db_id = parent.get('database_id', '').replace('-', '')
                        parent_ds_id = parent.get('data_source_id', '').replace('-', '')
                        
                        if parent_db_id == database_id:
                            if parent_ds_id:
                                found_data_source_id = parent_ds_id
                                print(f"\n✅ 找到了！")
                                print(f"Database ID: {database_id}")
                                print(f"Data Source ID: {parent_ds_id}")
                                print(f"\n在.env文件中使用: {parent_ds_id}")
                                return parent_ds_id
                    
                    if not found_data_source_id:
                        print(f"\n❌ 未找到 database_id={database_id} 的子项目")
                        print("可能的原因:")
                        print("  1. 数据库为空（没有任何条目）")
                        print("  2. 数据库未与集成共享")
                        print("  3. database_id 不正确")
                        return None
                        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n错误: 请提供 database_id")
        print("示例: python scripts/get_notion_datasource_id.py 1990d59debb781c58d78c302dffea2b5")
        sys.exit(1)
    
    database_id = sys.argv[1]
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    data_source_id = asyncio.run(find_data_source_id(database_id))
    
    if not data_source_id:
        sys.exit(1)

if __name__ == "__main__":
    main()
