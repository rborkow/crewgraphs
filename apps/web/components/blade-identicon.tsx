import { bladeSignature } from "@/lib/blade";

export interface BladeIdenticonProps {
  /** The org_id string — the sole determinant of the blade. */
  orgId: string;
  /** Rendered pixel size (square). Directory rows ~24, identity headers ~48. */
  size?: number;
  className?: string;
  /**
   * Optional accessible label. Omitted by default: the blade is a decorative
   * identity mark and the org name is always rendered alongside it, so it is
   * `aria-hidden` unless a caller explicitly needs it announced.
   */
  title?: string;
}

// Parallelogram "blade face" with a slight forward rake, in a 48×48 field.
const BL = { x: 12, y: 41 };
const BR = { x: 34, y: 41 };
const TR = { x: 42, y: 9 };
const TL = { x: 20, y: 9 };
const BLADE_PATH = `M${BL.x} ${BL.y} L${BR.x} ${BR.y} L${TR.x} ${TR.y} L${TL.x} ${TL.y} Z`;

// Spine axis endpoints (centres of the two width edges).
const BOTTOM_C = { x: (BL.x + BR.x) / 2, y: BL.y }; // (23, 41)
const TOP_C = { x: (TL.x + TR.x) / 2, y: TL.y }; // (31, 9)

export function BladeIdenticon({ orgId, size = 24, className, title }: BladeIdenticonProps) {
  const { geometry, field, mark, orientation } = bladeSignature(orgId);
  const uid = `blade-${orgId.replace(/[^a-zA-Z0-9]/g, "")}-${size}`;
  const clipId = `${uid}-clip`;

  const a11y = title
    ? ({ role: "img", "aria-label": title } as const)
    : ({ "aria-hidden": true, focusable: false } as const);

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...a11y}
    >
      {title ? <title>{title}</title> : null}
      <defs>
        <clipPath id={clipId}>
          <path d={BLADE_PATH} />
        </clipPath>
      </defs>

      <g clipPath={`url(#${clipId})`}>
        {/* Field */}
        <rect x="0" y="0" width="48" height="48" fill={field} />

        {geometry === "solid" && (
          // Centre spine, raked with the blade.
          <polygon
            points={`${BOTTOM_C.x - 3},${BOTTOM_C.y} ${BOTTOM_C.x + 3},${BOTTOM_C.y} ${TOP_C.x + 3},${TOP_C.y} ${TOP_C.x - 3},${TOP_C.y}`}
            fill={mark}
          />
        )}

        {geometry === "tip-band" && <rect x="0" y="9" width="48" height="9" fill={mark} />}

        {geometry === "diagonal-sash" && (
          <rect
            x="-8"
            y="20.5"
            width="64"
            height="9"
            fill={mark}
            transform={`rotate(${orientation === 0 ? -34 : 34} 24 24)`}
          />
        )}

        {geometry === "split-halves" &&
          (orientation === 0 ? (
            <polygon
              points={`${BOTTOM_C.x},${BOTTOM_C.y} ${BR.x},${BR.y} ${TR.x},${TR.y} ${TOP_C.x},${TOP_C.y}`}
              fill={mark}
            />
          ) : (
            <polygon
              points={`${BL.x},${BL.y} ${BOTTOM_C.x},${BOTTOM_C.y} ${TOP_C.x},${TOP_C.y} ${TL.x},${TL.y}`}
              fill={mark}
            />
          ))}

        {geometry === "chevron" &&
          (orientation === 0 ? (
            <path d="M16 28 L27 36 L38 28" fill="none" stroke={mark} strokeWidth="5" strokeLinejoin="round" strokeLinecap="round" />
          ) : (
            <path d="M16 32 L27 24 L38 32" fill="none" stroke={mark} strokeWidth="5" strokeLinejoin="round" strokeLinecap="round" />
          ))}
      </g>

      {/* Crisp edge so light fields still read against paper. */}
      <path d={BLADE_PATH} fill="none" stroke="#0E1B2C" strokeOpacity="0.35" strokeWidth="1.25" strokeLinejoin="round" />
    </svg>
  );
}
