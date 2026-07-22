import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { BladeIdenticon } from "./blade-identicon";
import { bladeSignature } from "@/lib/blade";

const A = "00000000-0000-4000-8000-000000000101";
const B = "00000000-0000-4000-8000-000000000102";

// The 12 fixture org_ids — they differ only in trailing digits, the hardest
// case for a hash-driven identicon.
const FIXTURE_IDS = Array.from(
  { length: 12 },
  (_, i) => `00000000-0000-4000-8000-0000000001${(i + 1).toString().padStart(2, "0")}`
);

function svg(orgId: string): string {
  const { container } = render(<BladeIdenticon orgId={orgId} size={48} />);
  return container.innerHTML;
}

describe("BladeIdenticon", () => {
  it("is deterministic: the same id renders identical SVG", () => {
    expect(svg(A)).toBe(svg(A));
  });

  it("renders different pattern/colours for different ids", () => {
    expect(svg(A)).not.toBe(svg(B));
  });

  it("is decorative (aria-hidden) by default, labelled when a title is given", () => {
    const { container: bare } = render(<BladeIdenticon orgId={A} />);
    expect(bare.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");

    const { getByRole } = render(<BladeIdenticon orgId={A} title="Millbrook blade" />);
    expect(getByRole("img", { name: "Millbrook blade" })).toBeInTheDocument();
  });

  it("gives the 12 fixture orgs 12 visually distinct blades", () => {
    const combos = new Set(
      FIXTURE_IDS.map((id) => {
        const s = bladeSignature(id);
        return `${s.geometry}|${s.fieldName}|${s.markName}`;
      })
    );
    expect(combos.size).toBe(FIXTURE_IDS.length);
  });

  it("uses both colours in every geometry (no single-colour collisions)", () => {
    for (const id of FIXTURE_IDS) {
      const { field, mark } = bladeSignature(id);
      expect(field).not.toBe(mark);
    }
  });
});
