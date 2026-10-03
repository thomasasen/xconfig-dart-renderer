export function clampNumber(value, min, max, fallback = 0) {
  const n = Number(value);
  const v = Number.isFinite(n) ? n : Number(fallback) || 0;
  return Math.min(max, Math.max(min, v));
}

export function normalizeCoverage(value, fallback = 1) {
  return clampNumber(value, 0.15, 1, fallback);
}

/**
 * Resolve a visually continuous barrel -> shaft/rear seam.
 *
 * Component textures are alpha-trimmed product-image extracts. Their visible silhouette
 * does not necessarily occupy the full texture height at the join edge. Therefore using
 * only nominal component diameters can create an artificial step. We choose the smaller
 * source-supported visible diameter and derive transparent mesh envelopes for both sides
 * so that the *visible* silhouette meets at the same thickness.
 */
export function resolveBarrelRearSeam({
  barrelDiameterMm,
  rearDiameterMm,
  barrelRearCoverage = 1,
  rearFrontCoverage = 1,
  targetVisibleDiameterMm = null,
} = {}) {
  const barrelDiameter = Math.max(0.2, Number(barrelDiameterMm) || 0.2);
  const rearDiameter = Math.max(0.2, Number(rearDiameterMm) || 0.2);
  const bCoverage = normalizeCoverage(barrelRearCoverage);
  const rCoverage = normalizeCoverage(rearFrontCoverage);

  const sourceVisibleBarrel = barrelDiameter * bCoverage;
  const sourceVisibleRear = rearDiameter * rCoverage;
  const requestedTarget = Number(targetVisibleDiameterMm);
  // At the physical rear connection the visible barrel neck and the visible shaft/rear
  // should meet at the rear component's nominal outside diameter. The mesh envelopes
  // may be wider because transparent padding in source-grounded textures is ignored.
  const visibleDiameterMm = Number.isFinite(requestedTarget) && requestedTarget > 0
    ? requestedTarget
    : rearDiameter;

  const barrelEndEnvelopeMm = visibleDiameterMm / bCoverage;
  const rearStartEnvelopeMm = visibleDiameterMm / rCoverage;

  return {
    visibleDiameterMm,
    barrelEndEnvelopeMm,
    rearStartEnvelopeMm,
    barrelRearCoverage: bCoverage,
    rearFrontCoverage: rCoverage,
    barrelVisibleAtJoinMm: barrelEndEnvelopeMm * bCoverage,
    rearVisibleAtJoinMm: rearStartEnvelopeMm * rCoverage,
    visibleDeltaMm: Math.abs(
      barrelEndEnvelopeMm * bCoverage - rearStartEnvelopeMm * rCoverage
    ),
  };
}

export function rotatePointAroundPivot(point, rotationDeg, pivot = { x: 0, y: 212 }) {
  const angle = (Number(rotationDeg) || 0) * Math.PI / 180;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  const x = Number(point?.x) || 0;
  const y = Number(point?.y) || 0;
  const px = Number(pivot?.x) || 0;
  const py = Number(pivot?.y) || 0;
  const dx = x - px;
  const dy = y - py;
  return {
    x: px + dx * cos - dy * sin,
    y: py + dx * sin + dy * cos,
  };
}
