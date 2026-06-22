import { describe, it, expect, vi } from "vitest";
import { JobSchema, validate } from "@/lib/schemas";

describe("response drift validation", () => {
  it("passes a valid job with no warning (extra fields allowed)", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const job = { id: 1, title: "Engineer", status: "Active", extra: true };
    expect(validate(JobSchema, job, "test")).toBe(job);
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  it("warns on drift but returns the data unchanged (non-fatal)", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const bad = { id: "not-a-number" } as unknown as { id: number };
    expect(validate(JobSchema, bad, "test")).toBe(bad);
    expect(warn).toHaveBeenCalledOnce();
    warn.mockRestore();
  });
});
