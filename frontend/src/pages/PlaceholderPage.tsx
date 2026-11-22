export interface PlaceholderPageProps {
  title: string;
  description: string;
}

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-3xl font-bold text-foreground">{title}</h1>
      <p className="text-muted">{description}</p>
      <p className="text-muted">This page is being built.</p>
    </section>
  );
}
