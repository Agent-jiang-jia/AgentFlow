export interface HealthResponse {
  status: "healthy";
  service: string;
  version: string;
  database: "ok";
}

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    candidate.status === "healthy" &&
    typeof candidate.service === "string" &&
    typeof candidate.version === "string" &&
    candidate.database === "ok"
  );
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(`后端健康检查失败（HTTP ${response.status}）`);
  }

  const payload: unknown = await response.json();
  if (!isHealthResponse(payload)) {
    throw new Error("后端健康检查返回了无效数据");
  }
  return payload;
}
