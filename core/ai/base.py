"""AI client abstract interface."""


class AIClient:
    """Base class for AI provider clients."""

    def generate_chat(self, system_prompt, user_content, temperature=0.7, enable_thinking=False):
        raise NotImplementedError

    def generate_chat_stream(self, system_prompt, user_content, temperature=0.7, enable_thinking=False):
        raise NotImplementedError
