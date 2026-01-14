import os
from zhipuai import ZhipuAI

# Temporary hardcoded key for development (should move to env var later)
API_KEY = "e5b7337745954ee393a9edc0168d02f2.1EZ1y0pnVbLHhvkL"

class ZhipuClient:
    def __init__(self):
        self.client = ZhipuAI(api_key=API_KEY)
        self.model = "glm-4"  # Using GLM-4 as standard, or "glm-4-plus" if available

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
