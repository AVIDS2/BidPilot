import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { runPiAgent } from "./runtime.js";
import type { PiRunRequest, PiRuntimeEvent } from "./contracts.js";
import { createPiModelCatalog } from "./catalog.js";

const port = Number.parseInt(process.env.DOCPILOT_PI_AGENT_PORT ?? "8787", 10);
const host = process.env.DOCPILOT_PI_AGENT_HOST ?? "0.0.0.0";
const internalSecret = process.env.DOCPILOT_PI_INTERNAL_SECRET?.trim() ?? "";
const PENDING_ABORT_TTL_MS = 30_000;

type ActiveRun = {
  controller: AbortController;
  response: ServerResponse;
};

const activeRuns = new Map<string, ActiveRun>();
const pendingAborts = new Map<string, ReturnType<typeof setTimeout>>();

function closeAbortTransport(activeRun: ActiveRun): void {
  if (activeRun.response.writableEnded || activeRun.response.destroyed) return;
  // The durable API run is the cancellation boundary. Closing only this HTTP
  // response lets the API reconcile the run immediately while Pi finishes its
  // official abort cleanup in the background.
  activeRun.response.destroy();
}

function rememberPendingAbort(runId: string): void {
  const previous = pendingAborts.get(runId);
  if (previous) clearTimeout(previous);
  pendingAborts.set(
    runId,
    setTimeout(() => {
      pendingAborts.delete(runId);
    }, PENDING_ABORT_TTL_MS),
  );
}

function consumePendingAbort(runId: string, activeRun: ActiveRun): boolean {
  const timer = pendingAborts.get(runId);
  if (!timer) return false;
  clearTimeout(timer);
  pendingAborts.delete(runId);
  activeRun.controller.abort();
  closeAbortTransport(activeRun);
  return true;
}

function writeEvent(response: ServerResponse, event: PiRuntimeEvent): void {
  if (response.writableEnded || response.destroyed) return;
  try {
    response.write(`${JSON.stringify(event)}\n`);
  } catch {
    // The API may close the stream after a durable cancellation. The run is
    // still allowed to finish its official Pi abort and clean up in memory.
  }
}

function writeJson(response: ServerResponse, statusCode: number, body: Record<string, unknown>): void {
  response.writeHead(statusCode, { "content-type": "application/json" });
  response.end(JSON.stringify(body));
}

function hasInternalAuth(request: IncomingMessage): boolean {
  return Boolean(internalSecret) && request.headers.authorization === `Bearer ${internalSecret}`;
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
        trusted_extensions: ["bidpilot-governance", "bidpilot-skills", "bidpilot-subagents"],
      }),
    );
    return;
  }
  if (request.method === "GET" && request.url === "/v1/models/catalog") {
    try {
      const catalog = await createPiModelCatalog();
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify(catalog));
    } catch (error) {
      response.writeHead(503, { "content-type": "application/json" });
      response.end(JSON.stringify({ error: error instanceof Error ? error.message : "Pi model catalog unavailable" }));
    }
    return;
  }

  const pathname = new URL(request.url ?? "/", "http://pi-agent").pathname;
  const abortMatch = pathname.match(/^\/v1\/runs\/([^/]+)\/abort$/);
  if (request.method === "POST" && abortMatch) {
    if (!hasInternalAuth(request)) {
      writeJson(response, 401, { error: "unauthorized" });
      return;
    }
    const runId = decodeURIComponent(abortMatch[1]);
    const activeRun = activeRuns.get(runId);
    if (!activeRun) {
      // Cancellation can race the Worker between claiming the task and
      // opening the sidecar stream. Keep the intent briefly so a run that is
      // about to start is aborted as soon as it registers here.
      rememberPendingAbort(runId);
      writeJson(response, 202, { status: "abort_queued", run_id: runId });
      return;
    }
    activeRun.controller.abort();
    // Pi's official abort still owns session cleanup. The API must not wait
    // for an upstream provider that ignores AbortSignal, so close only this
    // run's transport and let the durable cancellation event finish the UI.
    closeAbortTransport(activeRun);
    writeJson(response, 202, { status: "abort_requested", run_id: runId });
    return;
  }

  if (request.method !== "POST" || request.url !== "/v1/runs") {
    writeJson(response, 404, { error: "not_found" });
    return;
  }
  if (!hasInternalAuth(request)) {
    writeJson(response, 401, { error: "unauthorized" });
    return;
  }
  let payload: PiRunRequest;
  try {
    payload = (await readJson(request)) as PiRunRequest;
  } catch {
    writeJson(response, 400, { error: "invalid_json" });
    return;
  }
  if (activeRuns.has(payload.runId)) {
    writeJson(response, 409, { error: "run_already_active", run_id: payload.runId });
    return;
  }
  const abortController = new AbortController();
  const activeRun: ActiveRun = { controller: abortController, response };
  activeRuns.set(payload.runId, activeRun);
  consumePendingAbort(payload.runId, activeRun);
  const abortOnResponseClose = () => {
    if (!response.writableEnded) abortController.abort();
  };
  response.once("close", abortOnResponseClose);
  response.writeHead(200, {
    "content-type": "application/x-ndjson; charset=utf-8",
    "cache-control": "no-cache, no-transform",
    connection: "keep-alive",
  });
  try {
    await runPiAgent(payload, (event) => writeEvent(response, event), {}, abortController.signal);
  } catch (error) {
    writeEvent(response, {
      type: "agent.failed",
      error: error instanceof Error ? error.message : "Pi runtime failed",
    });
  } finally {
    response.off("close", abortOnResponseClose);
    if (activeRuns.get(payload.runId) === activeRun) activeRuns.delete(payload.runId);
    if (!response.writableEnded && !response.destroyed) response.end();
  }
});

server.listen(port, host, () => {
  process.stdout.write(`BidPilot Pi runtime listening on ${host}:${port}\n`);
});
