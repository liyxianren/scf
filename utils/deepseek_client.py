import os
import time
import httpx
from openai import OpenAI

# DeepSeek API Key
API_KEY = "sk-0af9934de1004b1ab60009edcbd98a42"
BASE_URL = "https://api.deepseek.com"

class DeepSeekClient:
    def __init__(self):
        # Set explicit timeout to avoid indefinite hangs
        self.client = OpenAI(
            api_key=API_KEY, 
            base_url=BASE_URL,
            timeout=httpx.Timeout(300.0, connect=30.0)  # 300s for request, 30s for connect
        )
        self.model = "deepseek-reasoner"  # Use reasoner for thinking mode
        self.model_chat = "deepseek-chat"  # Use chat for non-thinking mode

    def generate_chat(self, system_prompt, user_content, temperature=0.7, enable_thinking=False):
        """
        Generic wrapper for chat completions (non-streaming)
        Note: DeepSeek ignores temperature in thinking mode
        """
        start_time = time.time()
        model = self.model if enable_thinking else self.model_chat
        
        print(f"\n[DeepSeekClient] === API Call Start ===")
        print(f"[DeepSeekClient] Model: {model}")
        print(f"[DeepSeekClient] Enable Thinking: {enable_thinking}")
        print(f"[DeepSeekClient] System Prompt Length: {len(system_prompt)} chars")
        print(f"[DeepSeekClient] User Content Length: {len(user_content)} chars")
        
        try:
            params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "max_tokens": 8192
            }
            
            # Add thinking parameter for deepseek-chat model
            if enable_thinking and model == self.model_chat:
                params["extra_body"] = {"thinking": {"type": "enabled"}}
            
            print(f"[DeepSeekClient] Sending request...")
            response = self.client.chat.completions.create(**params)
            
            elapsed = time.time() - start_time
            print(f"[DeepSeekClient] Response received in {elapsed:.2f}s")
            
            if response and response.choices:
                content = response.choices[0].message.content
                print(f"[DeepSeekClient] Response Length: {len(content) if content else 0} chars")
                print(f"[DeepSeekClient] Response Preview: {content[:200] if content else 'EMPTY'}...")
                print(f"[DeepSeekClient] === API Call End (SUCCESS) ===\n")
                return content
            else:
                print(f"[DeepSeekClient] ERROR: Empty response or no choices!")
                print(f"[DeepSeekClient] Response object: {response}")
                print(f"[DeepSeekClient] === API Call End (EMPTY) ===\n")
                return None
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[DeepSeekClient] ERROR after {elapsed:.2f}s: {e}")
            import traceback
            print(f"[DeepSeekClient] Traceback:\n{traceback.format_exc()}")
            print(f"[DeepSeekClient] === API Call End (ERROR) ===\n")
            return None

    def generate_chat_stream(self, system_prompt, user_content, temperature=0.7, enable_thinking=False):
        """
        Streaming wrapper for chat completions
        Yields dicts: {"type": "thinking"|"content", "content": "..."}
        """
        try:
            model = self.model if enable_thinking else self.model_chat
            params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "max_tokens": 8192,
                "stream": True,
            }

            # Add thinking parameter for deepseek-chat model
            if enable_thinking and model == self.model_chat:
                params["extra_body"] = {"thinking": {"type": "enabled"}}

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
                print(f"Error calling DeepSeek stream: {e}")
                print(f"Traceback: {traceback.format_exc()}")
            except:
                pass
            return
