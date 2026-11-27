import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, isAbortError } from "./client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function csvResponse(filename: string | null, content = "a,b\n1,2\n"): Response {
  const headers: Record<string, string> = { "Content-Type": "text/csv" };
  if (filename) headers["Content-Disposition"] = `attachment; filename="${filename}"`;
  return new Response(content, { status: 200, headers });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("returns parsed payloads", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ app: { name: "Demo" } })));

    await expect(api.meta()).resolves.toEqual({ app: { name: "Demo" } });
  });

  it("turns the error envelope into an ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "DATASET_NOT_CLEANED",
              message: "Clean the dataset before using the dashboard.",
              details: { session_id: "s1" },
            },
          },
          409,
        ),
      ),
    );

    const error: unknown = await api.overview("s1").then(
      () => null,
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    if (!(error instanceof ApiError)) throw new Error("Expected an ApiError");
    expect(error.status).toBe(409);
    expect(error.code).toBe("DATASET_NOT_CLEANED");
    expect(error.message).toBe("Clean the dataset before using the dashboard.");
    expect(error.details).toEqual({ session_id: "s1" });
  });

  it("falls back to HTTP_ERROR when the body is not an envelope", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("bad gateway", { status: 502 })));

    const error: unknown = await api.meta().then(
      () => null,
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    if (!(error instanceof ApiError)) throw new Error("Expected an ApiError");
    expect(error.code).toBe("HTTP_ERROR");
    expect(error.status).toBe(502);
    expect(error.message).toContain("502");
  });

  it("reports an unreachable API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const error: unknown = await api.meta().then(
      () => null,
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    if (!(error instanceof ApiError)) throw new Error("Expected an ApiError");
    expect(error.status).toBe(0);
    expect(error.code).toBe("NETWORK_ERROR");
  });

  it("leaves aborts untouched", async () => {
    const abortError = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError));

    await expect(api.meta()).rejects.toBe(abortError);
    expect(isAbortError(abortError)).toBe(true);
    expect(isAbortError(new Error("nope"))).toBe(false);
  });

  it("resolves 204 responses without a body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    await expect(api.deleteSession("s1")).resolves.toBeUndefined();
  });
});

describe("downloads", () => {
  it("reads the frozen filename and the CSV bytes", async () => {
    const filename = "sales_demo_cleaned_20260101_120000.csv";
    const fetchMock = vi.fn().mockResolvedValue(csvResponse(filename));
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.download("s1", "cleaned");

    expect(result.filename).toBe(filename);
    expect(await result.blob.text()).toBe("a,b\n1,2\n");
    expect(fetchMock).toHaveBeenCalledWith("/api/datasets/s1/exports/cleaned", {
      method: "GET",
    });
  });

  it("posts the filter selection for the filtered export", async () => {
    const fetchMock = vi.fn().mockResolvedValue(csvResponse("filtered.csv"));
    vi.stubGlobal("fetch", fetchMock);

    await api.download("s1", "filtered", {
      preset: "last_90_days",
      search: "desk",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/datasets/s1/exports/filtered",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset: "last_90_days", search: "desk" }),
      }),
    );
  });

  it("falls back to a predictable filename", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(csvResponse(null)));

    const result = await api.download("s1", "quality-report");

    expect(result.filename).toBe("sales_quality-report.csv");
  });

  it("surfaces API errors during downloads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "DATASET_NOT_CLEANED",
              message: "Clean the dataset before downloading.",
            },
          },
          409,
        ),
      ),
    );

    await expect(api.download("s1", "cleaned")).rejects.toMatchObject({
      code: "DATASET_NOT_CLEANED",
      status: 409,
    });
  });
});
