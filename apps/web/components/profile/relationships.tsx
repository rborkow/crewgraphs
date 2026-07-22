import Link from "next/link";
import type { OrgProfilePayload } from "@crewgraphs/contracts";
import { relationshipTypeLabel } from "@/lib/profile-format";

/**
 * Related organizations from the identity graph — e.g. "Boosters for Bayward
 * Community Rowing". Quiet list; links when the other org has a profile.
 * Renders nothing when there are no relationships.
 */
export function Relationships({
  relationships
}: {
  relationships: OrgProfilePayload["relationships"];
}) {
  if (relationships.length === 0) return null;

  return (
    <section className="border-b border-mist py-8">
      <h2 className="eyebrow">Relationships</h2>
      <ul className="mt-3 flex flex-col gap-2 text-sm">
        {relationships.map((rel, index) => (
          <li key={`${rel.relationship_type}-${rel.other_org_slug ?? index}`} className="text-river">
            <span className="text-muted">{relationshipTypeLabel(rel.relationship_type)} </span>
            {rel.other_org_slug ? (
              <Link href={`/org/${rel.other_org_slug}`} className="hover:underline">
                {rel.other_display_name}
              </Link>
            ) : (
              <span className="font-medium">{rel.other_display_name}</span>
            )}
            {rel.note ? <span className="text-muted"> — {rel.note}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
