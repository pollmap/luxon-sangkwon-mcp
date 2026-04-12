"""
Luxon Sangkwon MCP Server - HTTP/SSE Entry Point.

한국 상권 인텔리전스 MCP 서버.
8 도구 / 4개 서버 / 3개 어댑터를 HTTP 엔드포인트로 제공.

Usage:
    # Streamable HTTP (권장)
    python server.py --transport streamable-http --port 8102

    # stdio (로컬 Claude Code용)
    python server.py --transport stdio

Environment:
    KAKAO_REST_API_KEY  - 카카오 로컬 API
    DATA_GO_KR_API_KEY  - 공공데이터포털
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("luxon-sangkwon-mcp")


def create_server():
    """Create the unified gateway MCP server."""
    from mcp_servers.gateway.gateway_server import GatewayServer
    gateway = GatewayServer()
    return gateway.mcp


def main():
    parser = argparse.ArgumentParser(description="Luxon Sangkwon MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http", "http"],
        default=os.getenv("MCP_TRANSPORT", "streamable-http"),
        help="Transport protocol (default: streamable-http)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Host to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8102")),
        help="Port to bind (default: 8102)",
    )
    parser.add_argument(
        "--stateless",
        action="store_true",
        default=os.getenv("MCP_STATELESS", "false").lower() == "true",
        help="Run in stateless HTTP mode",
    )
    args = parser.parse_args()

    mcp = create_server()

    logger.info("Starting Luxon Sangkwon MCP Server")
    logger.info(f"  Transport: {args.transport}")
    logger.info(f"  Host: {args.host}:{args.port}")
    logger.info(f"  Stateless: {args.stateless}")

    # API key status
    keys = {
        "KAKAO": bool(os.getenv("KAKAO_REST_API_KEY")),
        "DATA_GO_KR": bool(os.getenv("DATA_GO_KR_API_KEY")),
    }
    for name, ok in keys.items():
        logger.info(f"  {name}: {'OK' if ok else 'MISSING'}")

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport=args.transport,
            host=args.host,
            port=args.port,
            stateless=args.stateless,
        )


if __name__ == "__main__":
    main()
