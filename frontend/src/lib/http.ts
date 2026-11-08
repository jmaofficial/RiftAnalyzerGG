export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public retryAfter: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const base = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, init);
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError("Unable to connect. Please try again in a moment.", 0);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const retry = Number(response.headers.get("Retry-After"));
    throw new ApiError(
      typeof body?.detail === "string"
        ? body.detail
        : "Something went wrong. Please try again.",
      response.status,
      Number.isFinite(retry) && retry > 0 ? retry : null,
    );
  }
  return response.json() as Promise<T>;
}
