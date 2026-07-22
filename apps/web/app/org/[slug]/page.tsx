import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import { getProfile, getRouteSlugs, resolveSlug } from "@/lib/profile-data";
import { orgTypeLabel } from "@/lib/format";
import { IdentityHeader } from "@/components/profile/identity-header";
import { SnapshotFacts } from "@/components/profile/snapshot-facts";
import { FinancialTrends } from "@/components/profile/financial-trends";
import { RegattaPlaceholder } from "@/components/profile/regatta-placeholder";
import { People } from "@/components/profile/people";
import { Relationships } from "@/components/profile/relationships";
import { SourcesFooter } from "@/components/profile/sources-footer";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export function generateStaticParams(): { slug: string }[] {
  // Current pages plus renamed-org slugs (which 301 to their current slug).
  return getRouteSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const profile = getProfile(slug);
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
  const resolution = resolveSlug(slug);

  if (resolution.kind === "not_found") notFound();
  if (resolution.kind === "redirect") permanentRedirect(`/org/${resolution.slug}`);

  const profile = getProfile(resolution.slug);
  if (!profile) notFound();

  const { header, snapshot, coverage, people, relationships, org_id } = profile;

  return (
    <main className="mx-auto w-full max-w-5xl px-5 sm:px-8">
      <IdentityHeader header={header} orgId={org_id} />
      <SnapshotFacts snapshot={snapshot} slug={resolution.slug} />
      <FinancialTrends
        slug={resolution.slug}
        coverage={coverage}
        coverageState={header.coverage_state}
      />
      <RegattaPlaceholder />
      {people.length > 0 ? <People people={people} slug={resolution.slug} /> : null}
      <Relationships relationships={relationships} />
      <SourcesFooter coverage={coverage} slug={resolution.slug} />
    </main>
  );
}
