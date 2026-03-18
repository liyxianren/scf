import time
from zhipuai import ZhipuAI
from .base import AIClient


class ZhipuClient(AIClient):
    def __init__(self, api_key=None):
        if api_key is None:
            from flask import current_app
            api_key = current_app.config.get('ZHIPU_API_KEY', '')
        self.client = ZhipuAI(api_key=api_key, timeout=300)
        self.model = "glm-4.7"

    def generate_chat(self, system_prompt, user_content, temperature=0.7, enable_thinking=False):
        start_time = time.time()
        print(f"\n[ZhipuClient] === API Call Start ===")
        print(f"[ZhipuClient] Model: {self.model}")
        print(f"[ZhipuClient] Temperature: {temperature}")
        print(f"[ZhipuClient] Enable Thinking: {enable_thinking}")
        print(f"[ZhipuClient] System Prompt Length: {len(system_prompt)} chars")
        print(f"[ZhipuClient] User Content Length: {len(user_content)} chars")

        try:
            params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": temperature,
                "max_tokens": 4096
            }

            if enable_thinking:
                params["thinking"] = {"type": "enabled"}

            print(f"[ZhipuClient] Sending request...")
            response = self.client.chat.completions.create(**params)

            elapsed = time.time() - start_time
            print(f"[ZhipuClient] Response received in {elapsed:.2f}s")

            if response and response.choices:
                content = response.choices[0].message.content
                print(f"[ZhipuClient] Response Length: {len(content) if content else 0} chars")
                print(f"[ZhipuClient] Response Preview: {content[:200] if content else 'EMPTY'}...")
                print(f"[ZhipuClient] === API Call End (SUCCESS) ===\n")
                return content
            else:
                print(f"[ZhipuClient] ERROR: Empty response or no choices!")
                print(f"[ZhipuClient] Response object: {response}")
                print(f"[ZhipuClient] === API Call End (EMPTY) ===\n")
                return None

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[ZhipuClient] ERROR after {elapsed:.2f}s: {e}")
            import traceback
            print(f"[ZhipuClient] Traceback:\n{traceback.format_exc()}")
            print(f"[ZhipuClient] === API Call End (ERROR) ===\n")
            return None

    def generate_chat_with_tools(self, messages, tools, tool_choice="auto", temperature=0.3):
        """Send a chat completion request with function calling support.

        Args:
            messages: Full message list [{"role": "...", "content": "..."}, ...]
            tools: Tool definitions (OpenAI-compatible format)
            tool_choice: "auto" | "none" | "required"
            temperature: float

        Returns:
            Raw Completion response object (caller inspects tool_calls).
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

    def generate_chat_stream(self, system_prompt, user_content, temperature=0.7, enable_thinking=False):
        try:
            params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": temperature,
                "max_tokens": 4096,
                "stream": True,
            }

            if enable_thinking:
                params["thinking"] = {"type": "enabled"}

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
            try:
                import traceback
                print(f"Error calling ZhipuAI stream: {e}")
                print(f"Traceback: {traceback.format_exc()}")
            except:
                pass
            return
