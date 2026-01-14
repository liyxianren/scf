import os
from zhipuai import ZhipuAI

# Temporary hardcoded key for development (should move to env var later)
API_KEY = "e5b7337745954ee393a9edc0168d02f2.1EZ1y0pnVbLHhvkL"

class ZhipuClient:
    def __init__(self):
        self.client = ZhipuAI(api_key=API_KEY)
        self.model = "glm-4.7"

    def generate_chat(self, system_prompt, user_content, temperature=0.7, enable_thinking=False):
        """
        Generic wrapper for chat completions
        """
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
                
            response = self.client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling ZhipuAI: {e}")
            return None

    def generate_chat_stream(self, system_prompt, user_content, temperature=0.7, enable_thinking=False):
        """
        Streaming wrapper for chat completions
        """
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
                content = getattr(delta, "content", None) if delta else None
                if content:
                    yield content
        except Exception as e:
            print(f"Error calling ZhipuAI stream: {e}")
            return
