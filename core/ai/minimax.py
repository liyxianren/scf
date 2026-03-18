"""MiniMax AI client — OpenAI-compatible SDK, supports function calling."""
import time
import httpx
from openai import OpenAI
from .base import AIClient

BASE_URL = "https://api.minimaxi.com/v1"


class MiniMaxClient(AIClient):
    def __init__(self, api_key=None):
        if api_key is None:
            from flask import current_app
            api_key = current_app.config.get('MINIMAX_API_KEY', '')
        self.client = OpenAI(
            api_key=api_key,
            base_url=BASE_URL,
            timeout=httpx.Timeout(300.0, connect=30.0),
        )
        self.model = "MiniMax-M2.5-highspeed"

    def generate_chat(self, system_prompt, user_content, temperature=0.7, enable_thinking=False):
        try:
            params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": 4096,
                "temperature": temperature,
            }
            if enable_thinking:
                params["extra_body"] = {"reasoning_split": True}

            response = self.client.chat.completions.create(**params)
            if response and response.choices:
                return response.choices[0].message.content
            return None
        except Exception as e:
            print(f"[MiniMaxClient] Error: {e}")
            return None

    def generate_chat_stream(self, system_prompt, user_content, temperature=0.7, enable_thinking=False):
        try:
            params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": 4096,
                "temperature": temperature,
                "stream": True,
            }
            if enable_thinking:
                params["extra_body"] = {"reasoning_split": True}

            response = self.client.chat.completions.create(**params)
            for chunk in response:
                if not chunk or not getattr(chunk, "choices", None):
                    continue
                delta = getattr(chunk.choices[0], "delta", None)
                if not delta:
                    continue
                reasoning = getattr(delta, "reasoning_content", None)
                content = getattr(delta, "content", None)
                if reasoning:
                    yield {"type": "thinking", "content": reasoning}
                if content:
                    yield {"type": "content", "content": content}
        except Exception as e:
            print(f"[MiniMaxClient] Stream error: {e}")
            return

    def generate_chat_with_tools(self, messages, tools, tool_choice="auto", temperature=0.3):
        """Send a chat completion with function calling support.

        Uses the OpenAI-compatible format. Returns the raw response object
        so the caller can inspect tool_calls.
        """
        params = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "temperature": temperature,
            "max_tokens": 4096,
        }
        return self.client.chat.completions.create(**params)
