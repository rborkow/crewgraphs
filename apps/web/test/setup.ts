import "@testing-library/jest-dom/vitest";

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
