export async function loadCatalog(url = './data/catalog.json') {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Catalog load failed: HTTP ${r.status}`);
  return r.json();
}

export function getComponent(catalog, type, id) {
  if (!id) return null;
  return catalog.components?.[type]?.[id] || null;
}

export function resolveAssembly(catalog, selection) {
  const point = getComponent(catalog, 'points', selection.pointId);
  const barrel = getComponent(catalog, 'barrels', selection.barrelId);
  const rearSystem = getComponent(catalog, 'rearSystems', selection.rearSystemId);
  const shaft = rearSystem ? null : getComponent(catalog, 'shafts', selection.shaftId);
  const flight = rearSystem ? null : getComponent(catalog, 'flights', selection.flightId);
  return { point, barrel, rearSystem, shaft, flight };
}
