"""测试 Vertex AI Express Mode 连接

验证环境配置并测试 Session 和 Memory 服务连接。
"""
from __future__ import annotations

import os
import asyncio
from dotenv import load_dotenv
from google.adk.sessions import VertexAiSessionService
from google.adk.memory import VertexAiMemoryBankService

load_dotenv()


async def test_express_mode():
  """测试 Express Mode 配置和服务连接"""
  # 检查环境变量
  api_key = os.getenv("GOOGLE_API_KEY")
  use_vertexai = os.getenv("GOOGLE_GENAI_USE_VERTEXAI")
  agent_engine_id = os.getenv("AGENT_ENGINE_ID")

  print("="*60)
  print("环境配置检查")
  print("="*60)
  print(f"GOOGLE_API_KEY: {'✅ 已设置' if api_key else '❌ 未设置'}")
  if api_key:
    print(f"  Key preview: {api_key[:10]}...{api_key[-6:]}")
  print(f"GOOGLE_GENAI_USE_VERTEXAI: {use_vertexai}")
  if use_vertexai != "TRUE":
    print("  ⚠️  Warning: Should be 'TRUE' for Express Mode")
  print(f"AGENT_ENGINE_ID: {agent_engine_id if agent_engine_id else '❌ 未设置'}")

  if not agent_engine_id:
    print("\n⚠️  请先运行 setup_agent_engine.py 创建 Agent Engine")
    print("   命令: python scripts/setup_agent_engine.py")
    return

  # 测试 Session Service
  print("\n" + "="*60)
  print("测试 Session Service")
  print("="*60)
  try:
    session_service = VertexAiSessionService(agent_engine_id=agent_engine_id)
    print("📡 Creating test session...")
    session = await session_service.create_session(
      app_name=agent_engine_id,
      user_id="test_user"
    )
    print(f"✅ Session 创建成功!")
    print(f"   Session object type: {type(session)}")
    # Session 对象可能有不同的属性结构，尝试打印一些常见属性
    if hasattr(session, 'name'):
      print(f"   Session name: {session.name}")
    if hasattr(session, 'user_id'):
      print(f"   User ID: {session.user_id}")
  except Exception as e:
    print(f"❌ Session 创建失败: {e}")
    import traceback
    traceback.print_exc()
    print("\n可能的原因:")
    print("  1. AGENT_ENGINE_ID 不正确")
    print("  2. API Key 无效或已过期")
    print("  3. Express Mode 配额已用完")
    return

  # 测试 Memory Service
  print("\n" + "="*60)
  print("测试 Memory Service")
  print("="*60)
  try:
    memory_service = VertexAiMemoryBankService(agent_engine_id=agent_engine_id)
    print("✅ Memory Service 初始化成功")
  except Exception as e:
    print(f"❌ Memory Service 初始化失败: {e}")

  print("\n" + "="*60)
  print("✅ Express Mode 配置验证完成！")
  print("="*60)
  print("\n下一步:")
  print("  1. 运行 'adk run smart_task_app' 启动 agent")
  print("  2. 运行 'pytest tests/integration/' 执行集成测试")


if __name__ == "__main__":
  asyncio.run(test_express_mode())
