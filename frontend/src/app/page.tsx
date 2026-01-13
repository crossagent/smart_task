"use client";

import { AgentState } from "@/lib/types";
import {
  useCoAgent,
  useFrontendTool,
} from "@copilotkit/react-core";
import { CopilotKitCSSProperties, CopilotSidebar } from "@copilotkit/react-ui";
import { useState } from "react";

export default function CopilotKitPage() {
  const [themeColor, setThemeColor] = useState("#6366f1");

  // 🪁 Frontend Actions: https://docs.copilotkit.ai/adk/frontend-actions
  useFrontendTool({
    name: "setThemeColor",
    parameters: [
      {
        name: "themeColor",
        description: "The theme color to set. Make sure to pick nice colors.",
        required: true,
      },
    ],
    handler({ themeColor }) {
      setThemeColor(themeColor);
    },
  });

  return (
    <main
      style={
        { "--copilot-kit-primary-color": themeColor } as CopilotKitCSSProperties
      }
    >
      <CopilotSidebar
        disableSystemMessage={true}
        clickOutsideToClose={false}
        defaultOpen={true}
        labels={{
          title: "Smart Task Assistant",
          initial: "👋 Hello! I can help you manage your daily tasks and schedule. Try asking 'What's on my todo list today?' or 'Schedule a meeting'.",
        }}
        suggestions={[
          {
            title: "Daily Todo",
            message: "What are my tasks for today?",
          },
          {
            title: "Add Task",
            message: "Add a task to buy groceries.",
          },
          {
            title: "Schedule",
            message: "Schedule a team meeting for tomorrow at 10am.",
          },
          {
            title: "Frontend Tools",
            message: "Set the theme to green.",
          },
        ]}
      >
        <YourMainContent themeColor={themeColor} />
      </CopilotSidebar>
    </main>
  );
}

function YourMainContent({ themeColor }: { themeColor: string }) {
  // 🪁 Shared State: https://docs.copilotkit.ai/adk/shared-state
  // Use generic agent name 'SmartTaskAgent' or whatever name ADKAgent uses. 
  // In main.py we wrapped `root_agent` (named 'SmartTaskAgent') with ADKAgent.
  // The ADK middleware often defaults checking the agent name.
  // We'll keep it simple for now.
  const { state } = useCoAgent<AgentState>({
    name: "SmartTaskAgent",
    initialState: {},
  });

  return (
    <div
      style={{ backgroundColor: themeColor }}
      className="h-screen flex justify-center items-center flex-col transition-colors duration-300"
    >
      <div className="bg-white p-8 rounded-xl shadow-xl max-w-md w-full text-center">
        <h1 className="text-2xl font-bold mb-4 text-gray-800">Smart Task App</h1>
        <p className="text-gray-600 mb-6">
          Your intelligent assistant for task management. Use the sidebar to interact.
        </p>
        <div className="text-sm text-gray-400">
          ADK + CopilotKit
        </div>
      </div>
    </div>
  );
}
