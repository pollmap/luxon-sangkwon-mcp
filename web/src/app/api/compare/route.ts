import { NextRequest, NextResponse } from "next/server";
import { callTool } from "../_lib/mcp-client";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const result = await callTool("sangkwon_compare", {
    locations: body.locations,
    radius_m: body.radius_m || 500,
    category: body.category || null,
  });
  return NextResponse.json(result);
}
