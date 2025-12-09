from datetime import datetime
from google.adk.agents.base_agent import CallbackContext

def inject_current_time(callback_context: CallbackContext):
    """Callback to inject current time into session state."""
    now = datetime.now()
    # Update session state with current date and time
    # Note: State keys must be strings.
    # We use 'current_date' based on standard practice for prompt injection.
    callback_context.session.state["current_date"] = now.strftime("%Y-%m-%d")
    callback_context.session.state["current_weekday"] = now.strftime("%A")
