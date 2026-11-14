// Pure example module (no DOM, no network). Real core modules arrive with F-073+.
export function describeHealth(body) {
  if (!body || body.status !== "ok") return "Backend unavailable.";
  return `Backend ok (app ${body.version}, mapping ${body.mapping_version}).`;
}
