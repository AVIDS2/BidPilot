import { createServer, type ServerResponse } from "node:http";
import { runPiAgent } from "./runtime.js";
import type { PiRunRequest, PiRuntimeEvent } from "./contracts.js";

const port = Number.parseInt(process.env.DOCPILOT_PI_AGENT_PORT ?? "8787", 10);
const host = process.env.DOCPILOT_PI_AGENT_HOST ?? "0.0.0.0";

function writeEvent(response: ServerResponse, event: PiRuntimeEvent): void {
  response.write(`${JSON.stringify(event)}\n`);
}

async function readJson(request: AsyncIterable<Uint8Array>): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) chunks.push(Buffer.from(chunk));
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

const server = createServer(async (request, response) => {
  if (request.method === "GET" && request.url === "/health") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        status: "ok",
        runtime: "pi-coding-agent-session",
        sandbox_profiles: ["governed_cloud"],
        host_tools: false,
        trusted_extensions: ["bidpilot-governance", "bidpilot-skills"],
      }),
    );
    return;
  }
  if (request.method !== "POST" || request.url !== "/v1/runs") {
    response.writeHead(404, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: "not_found" }));
    return;
  }
  response.writeHead(200, {
    "content-type": "application/x-ndjson; charset=utf-8",
    "cache-control": "no-cache, no-transform",
    connection: "keep-alive",
  });
  try {
    const payload = (await readJson(request)) as PiRunRequest;
    await runPiAgent(payload, (event) => writeEvent(response, event));
  } catch (error) {
    writeEvent(response, {
      type: "agent.failed",
      error: error instanceof Error ? error.message : "Pi runtime failed",
    });
  } finally {
    response.end();
  }
});

server.listen(port, host, () => {
  process.stdout.write(`BidPilot Pi runtime listening on ${host}:${port}\n`);
});
