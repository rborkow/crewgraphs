import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import { getProfile, getTrends, resolveSlug } from "@/lib/profile-data";
import { getPublishMeta } from "@/lib/directory";
import { orgTypeLabel } from "@/lib/format";
import { IdentityHeader } from "@/components/profile/identity-header";
import { SnapshotFacts } from "@/components/profile/snapshot-facts";
import { FinancialTrends } from "@/components/profile/financial-trends";
import { FinancialComposition } from "@/components/profile/financial-composition";
import { RegattaPlaceholder } from "@/components/profile/regatta-placeholder";
import { People } from "@/components/profile/people";
import { Relationships } from "@/components/profile/relationships";
import { SourcesFooter } from "@/components/profile/sources-footer";

// Profiles are rendered on demand from the published snapshot; an unknown slug
// 404s and a renamed org's old slug 308s to its current page.
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const profile = await getProfile(slug);
  if (!profile) return { title: "Organization — CrewGraphs" };

  const { header } = profile;
  const where = [header.city, header.state].filter(Boolean).join(", ");
  const descriptor = [orgTypeLabel(header.org_type), where].filter(Boolean).join(" in ");
  const description = `${header.display_name}${
    descriptor ? ` — ${descriptor}.` : "."
  } Canonical identity and IRS financial context, every figure traceable to its filing.`;

  return {
    title: `${header.display_name} — CrewGraphs`,
    description
  };
}

export default async function OrgProfilePage({ params }: PageProps) {
  const { slug } = await params;
  const resolution = await resolveSlug(slug);

  if (resolution.kind === "not_found") notFound();
  if (resolution.kind === "redirect") permanentRedirect(`/org/${resolution.slug}`);

  const [profile, trends, publishMeta] = await Promise.all([
    getProfile(resolution.slug),
    getTrends(resolution.slug),
    getPublishMeta()
  ]);
  if (!profile) notFound();

  const { header, snapshot, coverage, people, relationships, org_id } = profile;
  const dataThroughLabel = publishMeta?.data_through_label ?? "";

  return (
    <main className="mx-auto w-full max-w-5xl px-5 sm:px-8">
      <IdentityHeader header={header} orgId={org_id} />
      <SnapshotFacts snapshot={snapshot} slug={resolution.slug} />
      <FinancialTrends
        slug={resolution.slug}
        coverage={coverage}
        coverageState={header.coverage_state}
        trends={trends}
      />
      <FinancialComposition
        composition={trends.composition}
        coverage={coverage}
        slug={resolution.slug}
      />
      <RegattaPlaceholder />
      {people.length > 0 ? <People people={people} slug={resolution.slug} /> : null}
      <Relationships relationships={relationships} />
      <SourcesFooter coverage={coverage} slug={resolution.slug} dataThroughLabel={dataThroughLabel} />
    </main>
  );
}
