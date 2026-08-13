"""LLM 客户端：mock 模式走模板，真实模式走 openai 兼容接口（DeepSeek/混元/通义等）。

部署到 TCB 时：设 LLM_MOCK=false 并填 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 即可。
"""
from app.config import config


class LLMClient:
    def __init__(self):
        self.mock = config.LLM_MOCK
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
        return self._client

    def chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        if self.mock:
            return self._mock(system, user)
        resp = self._get_client().chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def _mock(self, system: str, user: str) -> str:
        role = system.strip().splitlines()[0] if system else "专家"
        return (
            f"> {role}\n\n"
            f"【Mock 分析】针对「{user[:60]}」\n\n"
            f"- 当前为本地验证模式，未接入真实 LLM。\n"
            f"- 部署到 TCB 后填入 LLM_API_KEY 即启用真实多视角分析。\n"
            f"- 框架已就位：并行调度、4 模块汇编、合规护栏均生效。\n"
        )
