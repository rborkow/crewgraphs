/**
 * BladeIdenticon logic — a deterministic "blade face" derived purely from an
 * org_id string. This is the spec-mandated placeholder for absent licensed
 * blade art (the `blade_state` gate) and the product's visual signature.
 *
 * Everything here is a pure function of the id: same id → same blade, and the
 * feature axes are drawn from independently-salted hashes so ids that differ by
 * only a trailing character (as the fixture org_ids do) still diverge cleanly.
 */

/** Classic blade geometries. Every geometry uses BOTH colors so no two blades
 *  collapse to a single-colour look. */
export const BLADE_GEOMETRIES = [
  "solid", // field face + a centre spine in the mark colour
  "tip-band", // a band across the tip (far end)
  "diagonal-sash", // a diagonal stripe
  "split-halves", // split down the loom axis: one half field, one half mark
  "chevron" // a bold chevron in the mark colour
] as const;

export type BladeGeometry = (typeof BLADE_GEOMETRIES)[number];

/** On-brand blade colours: the five design tokens plus one lifted navy
 *  ("steel"), all within the river / buoy / gold / neutral hue families. */
export const BLADE_COLORS = {
  river: "#0E1B2C",
  steel: "#2E4A66",
  buoy: "#E85D26",
  gold: "#C9A227",
  mist: "#D9E2EA",
  paper: "#F7F9FB"
} as const;

export type BladeColorName = keyof typeof BLADE_COLORS;

/** Ordered field/mark pairs, each chosen to always carry a strong contrast. */
export const BLADE_COLORWAYS: ReadonlyArray<readonly [BladeColorName, BladeColorName]> = [
  ["river", "buoy"],
  ["river", "gold"],
  ["buoy", "paper"],
  ["gold", "river"],
  ["steel", "gold"],
  ["steel", "buoy"],
  ["river", "mist"],
  ["buoy", "river"]
];

/** 32-bit FNV-1a. Small, stable, and available identically to the server. */
export function fnv1a(input: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

export interface BladeSignature {
  geometry: BladeGeometry;
  fieldName: BladeColorName;
  markName: BladeColorName;
  field: string;
  mark: string;
  /** 0 | 1 — flips the direction of asymmetric geometries (sash, chevron, split). */
  orientation: 0 | 1;
}

/**
 * Resolve the deterministic blade for an org id. Salted per-axis so correlated
 * ids do not produce correlated blades.
 */
export function bladeSignature(orgId: string): BladeSignature {
  const geometry = BLADE_GEOMETRIES[fnv1a(`g:${orgId}`) % BLADE_GEOMETRIES.length];
  const [fieldName, markName] = BLADE_COLORWAYS[fnv1a(`c:${orgId}`) % BLADE_COLORWAYS.length];
  const orientation = (fnv1a(`o:${orgId}`) % 2) as 0 | 1;
  return {
    geometry,
    fieldName,
    markName,
    field: BLADE_COLORS[fieldName],
    mark: BLADE_COLORS[markName],
    orientation
  };
}
