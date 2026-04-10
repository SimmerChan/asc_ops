# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
AscendC Operator Knowledge Base API Server
"""

import os
from pathlib import Path

# 设置默认环境变量
if not os.getenv("CHROMA_DB_PATH"):
    os.environ["CHROMA_DB_PATH"] = str(Path(__file__).parent.parent.parent / "data" / "chroma_db")


def main():
    """启动服务"""
    import uvicorn

    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║       AscendC Operator Knowledge Base - Server            ║
╠═══════════════════════════════════════════════════════════╣
║  API文档:  http://localhost:{port}/docs                     ║
║  健康检查: http://localhost:{port}/health                    ║
║  OpenAPI:  http://localhost:{port}/openapi.json              ║
╚═══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "asc_ops.app:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )


if __name__ == "__main__":
    main()
