export function slugify(value: string): string {
  return (
    value
      .replace(/\.[a-z0-9]+$/i, "")
      .replace(/[^a-z0-9_-]+/gi, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "") || "sprite-export"
  );
}
