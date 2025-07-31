# Type stubs for litellm.proxy
from typing import Any

class LLMRouter:
    model_list: list[dict[str, Any]] | None

proxy_server: Any
llm_router: LLMRouter | None
