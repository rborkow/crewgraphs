import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// The App Router hooks have no provider under jsdom. Stub next/navigation with
// an inert router and a stable empty search-params view so client components
// (the directory explorer) render in tests; interactions drive local state, and
// the router writes are no-ops here.
vi.mock("next/navigation", () => {
  const params = new URLSearchParams();
  return {
    useRouter: () => ({
      push: vi.fn(),
      replace: vi.fn(),
      prefetch: vi.fn(),
      back: vi.fn(),
      forward: vi.fn(),
      refresh: vi.fn()
    }),
    usePathname: () => "/",
    useSearchParams: () => params
  };
});

// jsdom lacks a handful of DOM APIs that Radix UI (focus scope, dismissable
// layer, remove-scroll) touches. Provide inert stand-ins so the SourceDrawer
// can open under test.
if (typeof window !== "undefined") {
  if (!window.matchMedia) {
    window.matchMedia = (query: string) =>
      ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false
      }) as unknown as MediaQueryList;
  }

  if (!("ResizeObserver" in window)) {
    (window as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }

  const proto = Element.prototype as unknown as Record<string, unknown>;
  proto.hasPointerCapture ||= () => false;
  proto.setPointerCapture ||= () => {};
  proto.releasePointerCapture ||= () => {};
  proto.scrollIntoView ||= () => {};
}
