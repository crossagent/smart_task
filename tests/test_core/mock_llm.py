# MockLlm Provider for ADK Testing
# Defines a local, in-memory LLM that returns pre-defined responses.
# Used for Agent Integration Testing (Type 2).

from typing import Any, AsyncGenerator, Dict, List, Optional
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types

class MockLlm(BaseLlm):
    """
    A Mock LLM that intercepts prompts and returns programmable responses.
    Triggered when model="mock/..." is used.
    """
    model: str = "mock/generic"
    
    # Store programmable behaviors (Pattern -> Response)
    # This acts as a simple "Router"
    # Format: { "keyword": "response_text" OR {"tool": "name", "args": {}} }
    _behaviors: Dict[str, Any] = {}

    @classmethod
    def supported_models(cls) -> List[str]:
        # Registers this class for any model name starting with "mock/"
        return [r"mock/.*"]
    
    @classmethod
    def set_behaviors(cls, behaviors: Dict[str, Any]):
        """Configure the mock to respond to specific keywords."""
        cls._behaviors = behaviors

    @classmethod
    def clear_behaviors(cls):
        cls._behaviors = {}

    def _generate_response(self, text_content: str) -> LlmResponse:
        """Decide what to return based on the input text."""
        
        # 1. Simple Keyword Matching
        for pattern, response in self._behaviors.items():
            if pattern.lower() in text_content.lower():
                # If response is a dict with 'tool', return a FunctionCall
                if isinstance(response, dict) and "tool" in response:
                    return LlmResponse(content=types.Content(
                        role="model",
                        parts=[types.Part(
                            function_call=types.FunctionCall(
                                name=response["tool"],
                                args=response.get("args", {})
                            )
                        )]
                    ))
                # Otherwise return text
                return LlmResponse(content=types.Content(
                    role="model",
                    parts=[types.Part(text=str(response))]
                ))
        
        # 2. Default Fallback
        return LlmResponse(content=types.Content(
            role="model",
            parts=[types.Part(text=f"[MockLlm] I received your message: {text_content[:50]}...")]
        ))

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """ADK Async Generation Interface"""
        
        # Extract the last user message
        if not llm_request.contents:
             yield self._generate_response("EMPTY_REQUEST")
             return

        last_content = llm_request.contents[-1]
        text_input = ""
        
        # Simple extraction of text parts
        for part in last_content.parts:
            if part.text:
                text_input += part.text
        
        # Generate Response
        response = self._generate_response(text_input)
        
        # Simulate "streaming" by just yielding the final result once
        # (ADK supports non-partial final chunks in stream mode too)
        yield response
