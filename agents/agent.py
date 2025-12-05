"""
Smart Task Agent - ADK Web Entry Point

This module exposes the root_agent for use with 'adk web' command.
The DispatcherAgent serves as the main entry point that routes requests
to appropriate workflows.
"""

from .dispatcher.agent import DispatcherAgent

# ADK web requires a 'root_agent' variable
root_agent = DispatcherAgent(name="SmartTaskAgent")
