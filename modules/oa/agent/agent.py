"""Schedule Agent — orchestrates MiniMax function calling for course management."""
import json

from core.ai.minimax import MiniMaxClient
from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS, execute_tool


def _serialize_message(msg) -> dict:
    """Convert an OpenAI-compatible response message to a plain dict."""
    d = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return d


class ScheduleAgent:
    """AI-powered course scheduling agent using MiniMax-M2.5 function calling."""

    MAX_ROUNDS = 8

    def __init__(self):
        self.client = MiniMaxClient()
        self.tools = ALL_TOOLS

    def run(self, messages, on_event=None):
        """Execute the agent loop.

        Args:
            messages: Conversation history [{"role": "user"/"assistant", "content": "..."}]
            on_event: Optional callback ``(event_type: str, data)`` for progress updates.

        Returns:
            dict with keys:
                response  - final text reply to the user
                proposal  - pending write-operation proposal (or None)
                messages  - updated conversation history (excludes system prompt)
        """
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(messages)
        proposal = None

        for round_num in range(self.MAX_ROUNDS):
            if on_event:
                on_event("thinking", f"思考中… (第{round_num + 1}轮)")

            try:
                response = self.client.generate_chat_with_tools(
                    messages=full_messages,
                    tools=self.tools,
                    tool_choice="auto",
                    temperature=0.3,
                )
            except Exception as e:
                return {
                    "response": f"AI 服务调用失败: {e}",
                    "proposal": None,
                    "messages": full_messages[1:],
                }

            choice = response.choices[0]
            assistant_msg = choice.message

            # Append assistant message to history
            full_messages.append(_serialize_message(assistant_msg))

            # If no tool calls, the AI is done
            if not assistant_msg.tool_calls:
                return {
                    "response": assistant_msg.content or "",
                    "proposal": proposal,
                    "messages": full_messages[1:],
                }

            # Execute each tool call
            for tc in assistant_msg.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    fn_args = {}

                if on_event:
                    on_event("tool_call", {"name": fn_name, "args": fn_args})

                result = execute_tool(fn_name, fn_args)

                # Capture write-operation proposals
                if result.get("requires_confirmation"):
                    proposal = result

                full_messages.append({
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                    "tool_call_id": tc.id,
                })

        # Safety: max rounds exceeded
        return {
            "response": "处理轮次超限，请尝试简化您的请求。",
            "proposal": proposal,
            "messages": full_messages[1:],
        }
