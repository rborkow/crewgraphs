import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  )
}));

vi.mock("next/headers", () => ({
  headers: vi.fn()
}));

vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  })
}));

vi.mock("@/lib/admin-data", () => ({
  getAdminCounts: vi.fn(async () => ({
    pendingCorrections: 3,
    openReviewTasks: 7
  }))
}));

import AdminPage from "./page";
import { headers } from "next/headers";
import { getAdminCounts } from "@/lib/admin-data";

const originalAdminDatabaseUrl = process.env.ADMIN_DATABASE_URL;

beforeEach(() => {
  vi.clearAllMocks();
  process.env.ADMIN_DATABASE_URL = "postgres://admin_ro:test@localhost/crewgraphs";
});

afterEach(() => {
  cleanup();
  if (originalAdminDatabaseUrl === undefined) delete process.env.ADMIN_DATABASE_URL;
  else process.env.ADMIN_DATABASE_URL = originalAdminDatabaseUrl;
});

describe("admin gate", () => {
  it("returns not found without the Cloudflare Access assertion header", async () => {
    vi.mocked(headers).mockResolvedValue(new Headers() as never);

    await expect(AdminPage()).rejects.toThrow("NEXT_NOT_FOUND");
    expect(getAdminCounts).not.toHaveBeenCalled();
  });

  it("renders counts when the assertion header and admin database URL are present", async () => {
    vi.mocked(headers).mockResolvedValue(
      new Headers({ "Cf-Access-Jwt-Assertion": "signed-assertion" }) as never
    );

    render(await AdminPage());

    expect(screen.getByRole("heading", { name: "Review queues" })).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(getAdminCounts).toHaveBeenCalledOnce();
  });
});
