import pytest
from unittest.mock import MagicMock, AsyncMock
from shared.plugins import MaxTurnsPlugin
from google.adk.models.llm_response import LlmResponse
from google.genai import types

@pytest.mark.asyncio
async def test_max_turns_plugin_under_limit():
    # Setup
    plugin = MaxTurnsPlugin(max_turns=3)
    
    # Mock Event and Session
    mock_event = MagicMock()
    mock_event.invocation_id = "inv-1"
    mock_event.author = "model"
    
    mock_session = MagicMock()
    mock_session.id = "task-1"
    # Only 1 model turn yet
    mock_session.events = [mock_event]
    
    mock_invocation_context = MagicMock()
    mock_invocation_context.invocation_id = "inv-1"
    mock_invocation_context.session = mock_session
    
    mock_callback_context = MagicMock()
    mock_callback_context.invocation_context = mock_invocation_context
    
    mock_request = MagicMock()
    
    # Run
    result = await plugin.before_model_callback(
        callback_context=mock_callback_context, 
        llm_request=mock_request
    )
    
    # Verify: Under limit, should return None to proceed
    assert result is None

@pytest.mark.asyncio
async def test_max_turns_plugin_at_limit():
    # Setup
    plugin = MaxTurnsPlugin(max_turns=3)
    
    # Mock Sessions with 3 model turns already
    mock_events = []
    for _ in range(3):
        e = MagicMock()
        e.invocation_id = "inv-1"
        e.author = "model"
        mock_events.append(e)
    
    mock_session = MagicMock()
    mock_session.id = "task-1"
    mock_session.events = mock_events
    
    mock_invocation_context = MagicMock()
    mock_invocation_context.invocation_id = "inv-1"
    mock_invocation_context.session = mock_session
    
    mock_callback_context = MagicMock()
    mock_callback_context.invocation_context = mock_invocation_context
    
    mock_request = MagicMock()
    
    # Mock the Hub API call (http notify) to avoid network errors in test
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Run
        result = await plugin.before_model_callback(
            callback_context=mock_callback_context, 
            llm_request=mock_request
        )
    
    # Verify: At limit, should return LlmResponse (short-circuit)
    assert isinstance(result, LlmResponse)
    assert "terminated" in result.content.parts[0].text
    assert "3 model turns" in result.content.parts[0].text
    assert result.finish_reason == types.FinishReason.STOP

from unittest.mock import patch
