import pytest
import httpx

@pytest.mark.parametrize("agent_name", [
    "Hub (MCP)",
    "PM Agent",
    "Task Planner",
    "Coder Expert",
    "Trader Expert",
    "Research Expert",
    "Risk Expert",
    "Data Expert",
])
def test_agent_connectivity(http_client, agent_urls, agent_name):
    """
    Standard pytest case to verify A2A connectivity for each agent.
    Checks that the service is reachable and returns a valid HTTP response.
    """
    url = f"{agent_urls[agent_name]}/"
    try:
        response = http_client.get(url, follow_redirects=True)
        # ADK api_server might return 404 on root if no handler is defined, 
        # but 404 still proves the server is up and responding.
        assert response.status_code in [200, 404]
        
        # If it returns 200, try to verify
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                data = response.json()
                assert isinstance(data, (dict, list))
            else:
                # Non-JSON 200 OK is acceptable for root-level heartbeat (e.g. Dashboard)
                pass
            
    except httpx.ConnectError:
        pytest.fail(f"Could not connect to {agent_name} at {url}. Is the world up?")
    except Exception as e:
        pytest.fail(f"Agent {agent_name} connectivity test failed: {str(e)}")

def test_mcp_server_identity(http_client):
    """Specific check for the Hub's MCP server identity."""
    url = "http://localhost:45666/" # Hub port
    response = http_client.get(url, follow_redirects=True)
    assert response.status_code == 200
    # Hub usually returns a dashboard (HTML) or info (JSON)
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        data = response.json()
        assert "status" in data or "agents" in data
    else:
        # If HTML, check for dashboard indicators
        assert "Dashboard" in response.text or "Smart Task" in response.text
