import { NextRequest, NextResponse } from "next/server";
import { callTool } from "../_lib/mcp-client";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const args: Record<string, unknown> = {
    category: body.category,
    top_n: body.top_n || 10,
  };
  if (body.city) args.city = body.city;
  const result = await callTool("sangkwon_hot_areas", args);
  return NextResponse.json(result);
}
