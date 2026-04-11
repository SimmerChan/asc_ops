#!/usr/bin/env python
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
LLM 模块集成验证脚本

验证 UnifiedLLMClient 与各 Provider 的实际连接
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加 src 目录到 path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


def test_provider_config(provider_name: str, api_key_var: str) -> bool:
    """检查 Provider 是否配置"""
    api_key = os.getenv(api_key_var)
    if api_key and api_key != "your_zhipu_api_key" and api_key != "your_minimax_api_key" and not api_key.startswith("sk-ant") and not api_key.startswith("sk-"):
        print(f"  [{provider_name}] API Key: {api_key[:10]}...")
        return True
    elif api_key and (api_key.startswith("sk-ant") or api_key.startswith("sk-")):
        print(f"  [{provider_name}] API Key: {api_key[:15]}...")
        return True
    else:
        print(f"  [{provider_name}] API Key: NOT CONFIGURED")
        return False


async def verify_provider(provider_name: str, api_key_var: str, model_var: str = None):
    """验证单个 Provider"""
    print(f"\n{'='*60}")
    print(f"验证 {provider_name} Provider")
    print("=" * 60)

    api_key = os.getenv(api_key_var)
    if not api_key or api_key in ["your_zhipu_api_key", "your_minimax_api_key"]:
        print(f"  [SKIP] {provider_name} API Key 未配置")
        return

    # 检查是否是有效的 key 格式
    if api_key.startswith("sk-ant") or api_key.startswith("sk-") or len(api_key) > 20:
        print(f"  [OK] API Key 格式有效")
    else:
        print(f"  [SKIP] API Key 格式可能无效: {api_key}")
        return

    try:
        from asc_ops.llm import UnifiedLLMClient, Message, MessageRole

        # 获取 API Base
        api_base_var = f"{provider_name.upper()}_API_BASE"
        api_base = os.getenv(api_base_var, "")

        print(f"  [INFO] 创建 UnifiedLLMClient (provider={provider_name}, base={api_base})")
        client = UnifiedLLMClient(provider=provider_name, api_key=api_key, api_base=api_base)

        # 构建测试消息
        messages = [
            Message(role=MessageRole.USER, content="请用一句话回复：Hello")
        ]

        print(f"  [INFO] 发送测试请求...")
        response = await client.chat(
            messages=messages,
            max_tokens=50,
            temperature=0.3,
        )

        print(f"  [SUCCESS] 响应内容: {response.content[:100]}...")
        print(f"  [INFO] Provider: {response.provider}")
        print(f"  [INFO] Model: {response.model}")
        if response.usage:
            print(f"  [INFO] Usage: input={response.usage.input_tokens}, output={response.usage.output_tokens}")

        await client.close()

    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")


async def test_extractor_integration():
    """测试 Extractor 与 LLM 集成"""
    print(f"\n{'='*60}")
    print("验证 Extractor LLM 集成")
    print("=" * 60)

    # 检查是否有任何 LLM 配置
    has_llm = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not has_llm:
        print("  [SKIP] 没有配置任何 LLM API Key")
        return

    from asc_ops.extractor.bug_extractor import BugExtractor
    from asc_ops.llm import UnifiedLLMClient

    provider = os.getenv("DEFAULT_PROVIDER", "anthropic")
    api_key = os.getenv(f"{provider.upper()}_API_KEY")

    if not api_key:
        print(f"  [SKIP] {provider} API Key 未配置")
        return

    print(f"  [INFO] 使用 Provider: {provider}")
    client = UnifiedLLMClient(provider=provider, api_key=api_key)

    extractor = BugExtractor(llm_client=client)

    pr_title = "fix: memory leak in Matmul operator"
    pr_body = """
    Root cause: buffer not released after computation completes
    Fix: added buffer.release() call in destructor

    Trigger conditions:
    - When Matmul operator is used in a loop
    - Memory grows continuously without cleanup
    """

    print(f"  [INFO] 测试 extract_async with use_llm=True")
    result = await extractor.extract_async(
        pr_title=pr_title,
        pr_body=pr_body,
        source_repo="ascend-cann",
        source_pr="9999",
        use_llm=True,
    )

    print(f"  [RESULT] extraction_success: {result.extraction_success}")
    print(f"  [RESULT] root_cause: {result.root_cause}")
    print(f"  [RESULT] fix_pattern: {result.fix_pattern}")
    print(f"  [RESULT] trigger_conditions: {result.trigger_conditions}")

    await client.close()


async def main():
    print("=" * 60)
    print("LLM 模块集成验证")
    print("=" * 60)

    # 检查配置
    print("\n[配置检查]")
    test_provider_config("Anthropic", "ANTHROPIC_API_KEY")
    test_provider_config("OpenAI", "OPENAI_API_KEY")
    test_provider_config("Zhipu", "ZHIPU_API_KEY")
    test_provider_config("MiniMax", "MINIMAX_API_KEY")

    # 按优先级验证 Provider
    default_provider = os.getenv("DEFAULT_PROVIDER", "anthropic")

    if os.getenv("ANTHROPIC_API_KEY") and default_provider == "anthropic":
        await verify_provider("anthropic", "ANTHROPIC_API_KEY")
    elif os.getenv("OPENAI_API_KEY"):
        await verify_provider("openai", "OPENAI_API_KEY")
    elif os.getenv("ZHIPU_API_KEY"):
        await verify_provider("zhipu", "ZHIPU_API_KEY")
    elif os.getenv("MINIMAX_API_KEY"):
        await verify_provider("minimax", "MINIMAX_API_KEY")
    else:
        print("\n[SKIP] 没有配置任何 LLM API Key")

    # 测试 Extractor 集成
    await test_extractor_integration()

    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
