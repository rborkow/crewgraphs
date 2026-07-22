import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-start justify-center gap-6 px-6">
      <h1 className="text-3xl font-semibold">CrewGraphs — rowing club reference. Coming soon.</h1>
      <Button type="button">Explore later</Button>
    </main>
  );
}
