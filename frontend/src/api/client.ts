interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    retryable: boolean;
  };
}

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryable: boolean;

  constructor({
    code,
    message,
    status,
    retryable = false,
  }: {
    code: string;
    message: string;
    status: number;
    retryable?: boolean;
  }) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.retryable = retryable;
  }
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const error = (value as Record<string, unknown>).error;
  if (typeof error !== "object" || error === null) {
    return false;
  }
  const candidate = error as Record<string, unknown>;
  return (
    typeof candidate.code === "string" &&
    typeof candidate.message === "string" &&
    typeof candidate.retryable === "boolean"
  );
}

export async function responseError(response: Response): Promise<ApiError> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (isErrorEnvelope(payload)) {
    return new ApiError({
      code: payload.error.code,
      message: payload.error.message,
      retryable: payload.error.retryable,
      status: response.status,
    });
  }
  return new ApiError({
    code: "HTTP_ERROR",
    message: `请求失败（HTTP ${response.status}）`,
    status: response.status,
  });
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
