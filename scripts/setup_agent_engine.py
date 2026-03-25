"""设置 Vertex AI Express Mode Agent Engine

运行此脚本一次以创建 Agent Engine 实例，并获取 AGENT_ENGINE_ID。
"""
from __future__ import annotations

import os
import vertexai
from vertexai import agent_engines
from dotenv import load_dotenv

load_dotenv()


def setup_agent_engine():
  """创建 Agent Engine 并返回 ID"""
  api_key = os.getenv("GOOGLE_API_KEY")
  if not api_key:
    raise ValueError("❌ GOOGLE_API_KEY not found in .env file")

  use_vertexai = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper()
  if use_vertexai != "TRUE":
    print("⚠️  Warning: GOOGLE_GENAI_USE_VERTEXAI is not set to TRUE")
    print(f"   Current value: {use_vertexai}")

  print("🔧 Initializing Vertex AI Client...")
  print(f"   API Key: {api_key[:10]}...{api_key[-6:]}")

  # 初始化 Vertex AI 客户端
  client = vertexai.Client(api_key=api_key)

  print("\n🚀 Creating Agent Engine...")
  # 创建 Agent Engine
  agent_engine = client.agent_engines.create(
    config={
      "display_name": "Smart Task Agent Engine",
      "description": "Agent Engine for Smart Task Session and Memory",
    }
  )

  # 获取 Agent Engine ID
  app_id = agent_engine.api_resource.name.split('/')[-1]

  print(f"\n✅ Agent Engine created successfully!")
  print(f"\n{'='*60}")
  print(f"Agent Engine ID: {app_id}")
  print(f"Display Name: Smart Task Agent Engine")
  print(f"{'='*60}")
  print(f"\n📝 Please add this line to your .env file:")
  print(f"\n   AGENT_ENGINE_ID={app_id}\n")

  return app_id


if __name__ == "__main__":
  try:
    setup_agent_engine()
  except Exception as e:
    print(f"\n❌ Error creating Agent Engine: {e}")
    print("\nPlease check:")
    print("  1. GOOGLE_API_KEY is correct and from Express Mode")
    print("  2. GOOGLE_GENAI_USE_VERTEXAI=TRUE in .env")
    print("  3. Network connection is working")
    raise
