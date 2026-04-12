import { NextRequest, NextResponse } from "next/server";
import { callTool } from "../_lib/mcp-client";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const args: Record<string, unknown> = {
    location: body.location,
    radius_m: body.radius_m || 1000,
    cell_size_m: body.cell_size_m || 100,
  };
  if (body.category) args.category = body.category;
  const result = await callTool("sangkwon_density_map", args);
  return NextResponse.json(result);
}
