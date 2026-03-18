from .deepseek import DeepSeekClient
from .zhipu import ZhipuClient
from .minimax import MiniMaxClient


def get_ai_client(provider='deepseek'):
    """Factory function to get an AI client by provider name."""
    if provider == 'deepseek':
        return DeepSeekClient()
    if provider in ('zhipu', 'chatglm'):
        return ZhipuClient()
    if provider == 'minimax':
        return MiniMaxClient()
    raise ValueError(f"Unknown AI provider: {provider}")
