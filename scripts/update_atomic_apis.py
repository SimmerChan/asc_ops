#!/usr/bin/env python3
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
更新 AscendC 原子操作 API 到知识库

从官方文档抓取原子操作API信息并存储到 ChromaDB
"""

import asyncio
import logging
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# 添加项目根目录到 path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.asc_ops.storage.chroma_client import ChromaDBClient
from src.asc_ops.collector.embedder import Embedder
from src.asc_ops.models import AscendCAPIDefinition, APIParameter, APIReturnValue, UsageExample, APISourceInfo

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# 原子操作 API 列表
ATOMIC_APIS = [
    {
        "name": "asc_atomic_add",
        "url": "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_10375.html",
        "category": "SIMT API",
        "subcategory": "Atomic函数",
    },
    {
        "name": "asc_atomic_sub",
        "url": "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_10376.html",
        "category": "SIMT API",
        "subcategory": "Atomic函数",
    },
    {
        "name": "asc_atomic_exch",
        "url": "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_10377.html",
        "category": "SIMT API",
        "subcategory": "Atomic函数",
    },
    {
        "name": "asc_atomic_max",
        "url": "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_10378.html",
        "category": "SIMT API",
        "subcategory": "Atomic函数",
    },
    {
        "name": "asc_atomic_min",
        "url": "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_10379.html",
        "category": "SIMT API",
        "subcategory": "Atomic函数",
    },
    {
        "name": "asc_atomic_inc",
        "url": "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_10380.html",
        "category": "SIMT API",
        "subcategory": "Atomic函数",
    },
    {
        "name": "asc_atomic_dec",
        "url": "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_10381.html",
        "category": "SIMT API",
        "subcategory": "Atomic函数",
    },
    {
        "name": "asc_atomic_cas",
        "url": "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_10382.html",
        "category": "SIMT API",
        "subcategory": "Atomic函数",
    },
    {
        "name": "asc_atomic_and",
        "url": "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_10383.html",
        "category": "SIMT API",
        "subcategory": "Atomic函数",
    },
    {
        "name": "asc_atomic_or",
        "url": "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_10384.html",
        "category": "SIMT API",
        "subcategory": "Atomic函数",
    },
    {
        "name": "asc_atomic_xor",
        "url": "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/atlasascendc_api_07_10385.html",
        "category": "SIMT API",
        "subcategory": "Atomic函数",
    },
]


def parse_atomic_api_content(name: str, content: str, url: str, category: str, subcategory: str) -> Optional[AscendCAPIDefinition]:
    """
    解析原子操作 API 页面内容

    Args:
        name: API 名称
        content: 页面文本内容
        url: 页面 URL
        category: 分类
        subcategory: 子分类

    Returns:
        AscendCAPIDefinition 对象
    """
    try:
        # 提取功能说明
        desc_match = re.search(r'功能说明\s*\n+(.+?)(?=\s*函数原型|需要包含的头文件|$)', content, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else ""

        # 提取函数原型
        signatures = []
        sig_match = re.search(r'函数原型\s*\n+(.+?)(?=\s*参数说明|需要包含的头文件|$)', content, re.DOTALL)
        if sig_match:
            sig_text = sig_match.group(1)
            for line in sig_text.strip().split('\n'):
                line = line.strip()
                if 'inline' in line or line.startswith('inline'):
                    signatures.append(line)

        if not signatures:
            # 尝试更宽松的匹配
            for line in content.split('\n'):
                if 'asc_atomic_' in line and '(' in line:
                    signatures.append(line.strip())

        # 提取参数说明
        parameters = []
        param_match = re.search(r'参数说明\s*\n+(?:表\d+\s*)?.*?\n+(.+?)(?=\s*返回值说明|约束说明|需要包含的头文件|$)', content, re.DOTALL)
        if param_match:
            param_text = param_match.group(1)
            # 解析参数表格
            param_lines = param_text.split('\n')
            current_param = None
            for line in param_lines:
                line = line.strip()
                if not line or line.startswith('参数名称') or line.startswith('输入/输出') or line.startswith('描述'):
                    continue
                if line.startswith('address') or line.startswith('val') or line.startswith('old') or line.startswith('compare') or line.startswith('mask'):
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        param_name = parts[0].strip()
                        param_desc = ' '.join([p.strip() for p in parts[1:] if p.strip()])
                        direction = "输入"
                        if param_name == "address":
                            direction = "输出"
                        parameters.append(APIParameter(
                            name=param_name,
                            direction=direction,
                            param_type="",
                            description=param_desc
                        ))

        # 提取返回值说明
        return_match = re.search(r'返回值说明\s*\n+(.+?)(?=\s*约束说明|需要包含的头文件|$)', content, re.DOTALL)
        return_value_desc = return_match.group(1).strip() if return_match else ""
        return_value = APIReturnValue(type="", description=return_value_desc)

        # 提取头文件
        headers = []
        header_match = re.search(r'需要包含的头文件\s*\n+(.+?)(?=\s*调用示例|$)', content, re.DOTALL)
        if header_match:
            header_text = header_match.group(1)
            for line in header_text.split('\n'):
                line = line.strip()
                if line.startswith('#include'):
                    headers.append(line.strip())

        # 提取约束说明
        constraint_match = re.search(r'约束说明\s*\n+(.+?)(?=\s*需要包含的头文件|调用示例|$)', content, re.DOTALL)
        constraints = []
        if constraint_match:
            constraint_text = constraint_match.group(1).strip()
            constraints.append(constraint_text)

        # 提取代码示例
        examples = []
        example_match = re.search(r'调用示例\s*\n+(?:SIMD与SIMT混合编程场景：\s*\n)?(.+?)(?=\s*上一篇|\Z)', content, re.DOTALL)
        if example_match:
            example_text = example_match.group(1).strip()
            # 提取代码块
            code_blocks = re.findall(r'(__simt_vf__.*?(?=\n\n|\Z))', example_text, re.DOTALL)
            for block in code_blocks:
                examples.append(UsageExample(
                    language="cpp",
                    code=block.strip(),
                    description="SIMD与SIMT混合编程场景"
                ))

        # 生成 API ID
        api_id = f"ascendc_{name}"

        # 构建描述文本（用于 embedding）
        doc_text = f"""API: {name} | 分类: {category}/{subcategory} | 描述: {description}

函数原型:
{chr(10).join(signatures)}

参数说明:
{chr(10).join([f"{p.name}: {p.description}" for p in parameters])}

返回值: {return_value.description}

约束: {chr(10).join(constraints)}

头文件: {chr(10).join(headers)}

示例:
{chr(10).join([ex.code for ex in examples])}
"""

        return AscendCAPIDefinition(
            api_id=api_id,
            name=name,
            signature='\n'.join(signatures) if signatures else "",
            parameters=parameters,
            return_value=return_value,
            description=description,
            category=category,
            subcategory=subcategory,
            hardware_support=["Atlas 350 加速卡"],
            constraints=constraints,
            usage_examples=examples,
            source_info=APISourceInfo(
                source_type="official_docs",
                url=url,
                collected_at="",
            ),
            document_text=doc_text,
        )

    except Exception as e:
        logger.error(f"Failed to parse {name}: {e}")
        return None


async def update_atomic_apis():
    """更新原子操作 API 到知识库"""
    logger.info("Starting atomic API update...")

    # 初始化 ChromaDB 客户端
    chroma_client = ChromaDBClient(persist_directory="data/chroma_db")

    # 初始化 embedder
    embedder = Embedder()

    # 获取 collection
    collection_name = "ascend_apis"
    try:
        collection = chroma_client.get_collection(collection_name)
    except Exception:
        logger.error(f"Collection {collection_name} not found")
        return

    # 批量存储
    ids = []
    documents = []
    metadatas = []
    embeddings = []

    for api_info in ATOMIC_APIS:
        name = api_info["name"]
        url = api_info["url"]
        category = api_info["category"]
        subcategory = api_info["subcategory"]

        logger.info(f"Processing {name}...")

        # 由于无法直接用脚本获取JS渲染后的内容，
        # 这里使用预定义的API信息
        # 在实际运行时，可以通过 MCP 工具获取完整内容

        # 跳过，等待用户提供实际内容
        logger.info(f"  Skipping {name} - need actual page content (use MCP tool to fetch)")

    logger.info(f"Atomic API update completed")


if __name__ == "__main__":
    asyncio.run(update_atomic_apis())
