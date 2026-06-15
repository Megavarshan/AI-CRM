"""
CRM router — AI Copilot.

POST /copilot/chat — agentic multi-turn chat with tool calling.

Responses are streamed as Server-Sent Events (SSE).
Each event has a `type`: 'text' | 'tool_call' | 'tool_result' | 'done'
"""

from __future__ import annotations

import json
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from deps import OrgContext, get_org
from services.ai_engine import copilot_chat

logger = logging.getLogger(__name__)

router = APIRouter()


class CopilotRequest(BaseModel):
    messages: list[dict]
    session_id: str | None = None


@router.post("/copilot/chat")
async def copilot_chat_endpoint(body: CopilotRequest, org: OrgContext = Depends(get_org)):
    """
    Agentic AI Copilot endpoint.

    Runs the tool-calling agent loop and streams SSE events back to the frontend
    so the user sees each reasoning step and tool call in real time.
    """
    async def event_stream():
        try:
            # We call the async generator copilot_chat (org-scoped)
            async for event in copilot_chat(body.messages, org.org_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Error in Copilot chat stream: {e}")
            yield f"data: {json.dumps({'type': 'text', 'content': f'An error occurred: {e}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
