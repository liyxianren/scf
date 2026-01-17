import os
import time
from zhipuai import ZhipuAI

# Temporary hardcoded key for development (should move to env var later)
API_KEY = "e5b7337745954ee393a9edc0168d02f2.1EZ1y0pnVbLHhvkL"

class ZhipuClient:
    def __init__(self):
        # Set explicit timeout to avoid indefinite hangs
        self.client = ZhipuAI(api_key=API_KEY, timeout=300)
        self.model = "glm-4.7"

    def generate_chat(self, system_prompt, user_content, temperature=0.7, enable_thinking=False):
        """
        Generic wrapper for chat completions
        """
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
