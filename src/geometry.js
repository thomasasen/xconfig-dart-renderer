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


export function smoothstep01(value) {
  const t = clampNumber(value, 0, 1, 0);
  return t * t * (3 - 2 * t);
}

/**
 * Build a short, smooth connection profile while keeping a constant section directly
 * at the physical join. The flat join section is deliberate: it makes the tangent at
 * the barrel/rear boundary zero on both sides, so equal visible diameters cannot still
 * meet with a visible V-shaped kink.
 */
export function buildSmoothJoinProfile({
  bodyDiameterMm,
  joinDiameterMm,
  lengthMm,
  side = 'rear',
  transitionMm = 3,
  flatJoinMm = 1,
  samples = 8,
} = {}) {
  const length = Math.max(0.1, Number(lengthMm) || 0.1);
  const body = Math.max(0.2, Number(bodyDiameterMm) || 0.2);
  const join = Math.max(0.2, Number(joinDiameterMm) || body);
  if (Math.abs(body - join) < 1e-9) return [[0, body], [1, body]];

  const flat = clampNumber(flatJoinMm, 0, Math.min(length * 0.25, 2), 1);
  const available = Math.max(0, length - flat);
  const transition = clampNumber(
    transitionMm,
    Math.min(0.25, available),
    Math.max(Math.min(available, length * 0.35), Math.min(0.25, available)),
    Math.min(3, available)
  );
  const count = Math.max(4, Math.min(24, Math.round(Number(samples) || 8)));
  const points = [];

  if (side === 'front') {
    const flatEnd = flat / length;
    const transitionEnd = Math.min(1, (flat + transition) / length);
    points.push([0, join], [flatEnd, join]);
    for (let i = 1; i <= count; i += 1) {
      const t = i / count;
      const u = flatEnd + (transitionEnd - flatEnd) * t;
      const diameter = join + (body - join) * smoothstep01(t);
      points.push([u, diameter]);
    }
    if (transitionEnd < 1) points.push([1, body]);
  } else {
    const flatStart = Math.max(0, (length - flat) / length);
    const transitionStart = Math.max(0, (length - flat - transition) / length);
    if (transitionStart > 0) points.push([0, body]);
    for (let i = 0; i < count; i += 1) {
      const t = i / count;
      const u = transitionStart + (flatStart - transitionStart) * t;
      const diameter = body + (join - body) * smoothstep01(t);
      points.push([u, diameter]);
    }
    points.push([flatStart, join], [1, join]);
  }

  const deduped = [];
  for (const [u, diameter] of points) {
    const clampedU = clampNumber(u, 0, 1, 0);
    if (deduped.length && Math.abs(deduped[deduped.length - 1][0] - clampedU) < 1e-9) {
      deduped[deduped.length - 1] = [clampedU, diameter];
    } else {
      deduped.push([clampedU, diameter]);
    }
  }
  return deduped;
}

export function profileEndpointSlope(profile, lengthMm, side = 'rear') {
  const length = Math.max(0.1, Number(lengthMm) || 0.1);
  const points = (Array.isArray(profile) ? profile : [])
    .map(([u, diameter]) => [Number(u), Number(diameter)])
    .filter(([u, diameter]) => Number.isFinite(u) && Number.isFinite(diameter))
    .sort((a, b) => a[0] - b[0]);
  if (points.length < 2) return 0;
  const [a, b] = side === 'front'
    ? [points[0], points[1]]
    : [points[points.length - 2], points[points.length - 1]];
  const dx = (b[0] - a[0]) * length;
  return Math.abs(dx) < 1e-12 ? 0 : (b[1] - a[1]) / dx;
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
