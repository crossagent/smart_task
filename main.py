"""
Smart Task - Main entry point for command-line execution.
For ADK web debugging, use: adk web .
"""

import asyncio
from agents.main import main

if __name__ == "__main__":
    asyncio.run(main())
