import { NextRequest, NextResponse } from "next/server";
import { callTool } from "../_lib/mcp-client";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const args: Record<string, unknown> = {
    location: body.location,
    category: body.category,
  };
  if (body.budget) args.budget = body.budget;
  const result = await callTool("sangkwon_startup_score", args);
  return NextResponse.json(result);
}
