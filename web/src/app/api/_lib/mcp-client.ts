/**
 * MCP Client — 매 요청마다 새 세션 생성 (stateless 모드).
 *
 * Next.js 서버 런타임에서 SSE 세션 재사용이 불안정하므로
 * 매 API 호출마다 initialize → tool call → 파싱 전체 수행.
 */

const MCP_URL = process.env.MCP_SERVER_URL || "http://127.0.0.1:8102/mcp";

const HEADERS = {
  "Content-Type": "application/json",
  Accept: "application/json, text/event-stream",
};

function parseSSE(text: string): Record<string, unknown> | null {
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (trimmed.startsWith("data:")) {
      try {
        const data = JSON.parse(trimmed.slice(5).trim());
        if (data.result?.content) {
          for (const c of data.result.content) {
            if (c.text) return JSON.parse(c.text);
          }
        }
        if (data.error) {
          return { error: true, message: data.error.message || "MCP error" };
        }
      } catch {
        continue;
      }
    }
  }
  return null;
}

export async function callTool(
  toolName: string,
  args: Record<string, unknown>
): Promise<Record<string, unknown>> {
  try {
    // Step 1: Initialize (new session every call)
    const initRes = await fetch(MCP_URL, {
      method: "POST",
      headers: HEADERS,
      cache: "no-store",
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: {
          protocolVersion: "2024-11-05",
          capabilities: {},
          clientInfo: { name: "sangkwon-web", version: "1.0" },
        },
      }),
    });

    const sid = initRes.headers.get("mcp-session-id") || "";
    const sessionHeaders = { ...HEADERS, "Mcp-Session-Id": sid };

    // Step 2: Initialized notification
    await fetch(MCP_URL, {
      method: "POST",
      headers: sessionHeaders,
      cache: "no-store",
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "notifications/initialized",
        params: {},
      }),
    });

    // Step 3: Call tool (with timeout to prevent SSE hanging)
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);

    const toolRes = await fetch(MCP_URL, {
      method: "POST",
      headers: sessionHeaders,
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 2,
        method: "tools/call",
        params: { name: toolName, arguments: args },
      }),
      signal: controller.signal,
    });

    const text = await toolRes.text();
    clearTimeout(timeout);
    const result = parseSSE(text);
    if (result) return result;

    // Debug: try parsing as plain JSON (non-SSE response)
    try {
      const plain = JSON.parse(text);
      if (plain.result?.content) {
        for (const c of plain.result.content) {
          if (c.text) return JSON.parse(c.text);
        }
      }
    } catch {
      // Not JSON either
    }

    return { error: true, message: "Failed to parse MCP response", debug_length: text.length, debug_preview: text.slice(0, 200) };
  } catch (e) {
    return { error: true, message: `MCP connection error: ${e}` };
  }
}
