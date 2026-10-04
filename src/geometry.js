export function clampNumber(value, min, max, fallback = 0) {
  const n = Number(value);
  const v = Number.isFinite(n) ? n : Number(fallback) || 0;
  return Math.min(max, Math.max(min, v));
}

export function normalizeCoverage(value, fallback = 1) {
  return clampNumber(value, 0.15, 1, fallback);
}

/**
 * Resolve two alpha-textured physical bodies to the same visible diameter at a join.
 * The nominal mesh envelopes may differ because transparent padding is ignored.
 */
export function resolveVisibleJoin({
  leftNominalDiameterMm,
  rightNominalDiameterMm,
  leftCoverage = 1,
  rightCoverage = 1,
  targetVisibleDiameterMm = null,
} = {}) {
  const leftDiameter = Math.max(0.2, Number(leftNominalDiameterMm) || 0.2);
  const rightDiameter = Math.max(0.2, Number(rightNominalDiameterMm) || 0.2);
  const lCoverage = normalizeCoverage(leftCoverage);
  const rCoverage = normalizeCoverage(rightCoverage);
  const requested = Number(targetVisibleDiameterMm);
  const visibleDiameterMm = Number.isFinite(requested) && requested > 0
    ? requested
    : rightDiameter;
  const leftEnvelopeMm = visibleDiameterMm / lCoverage;
  const rightEnvelopeMm = visibleDiameterMm / rCoverage;
  return {
    visibleDiameterMm,
    leftEnvelopeMm,
    rightEnvelopeMm,
    leftCoverage: lCoverage,
    rightCoverage: rCoverage,
    leftVisibleAtJoinMm: leftEnvelopeMm * lCoverage,
    rightVisibleAtJoinMm: rightEnvelopeMm * rCoverage,
    visibleDeltaMm: Math.abs(
      leftEnvelopeMm * lCoverage - rightEnvelopeMm * rCoverage
    ),
    sourceVisibleLeftMm: leftDiameter * lCoverage,
    sourceVisibleRightMm: rightDiameter * rCoverage,
  };
}

/**
 * Backward-compatible barrel -> rear seam wrapper.
 */
export function resolveBarrelRearSeam({
  barrelDiameterMm,
  rearDiameterMm,
  barrelRearCoverage = 1,
  rearFrontCoverage = 1,
  targetVisibleDiameterMm = null,
} = {}) {
  const join = resolveVisibleJoin({
    leftNominalDiameterMm: barrelDiameterMm,
    rightNominalDiameterMm: rearDiameterMm,
    leftCoverage: barrelRearCoverage,
    rightCoverage: rearFrontCoverage,
    targetVisibleDiameterMm,
  });
  return {
    visibleDiameterMm: join.visibleDiameterMm,
    barrelEndEnvelopeMm: join.leftEnvelopeMm,
    rearStartEnvelopeMm: join.rightEnvelopeMm,
    barrelRearCoverage: join.leftCoverage,
    rearFrontCoverage: join.rightCoverage,
    barrelVisibleAtJoinMm: join.leftVisibleAtJoinMm,
    rearVisibleAtJoinMm: join.rightVisibleAtJoinMm,
    visibleDeltaMm: join.visibleDeltaMm,
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

export function buildSmoothBridgeProfile({
  frontDiameterMm,
  rearDiameterMm,
  lengthMm,
  flatFrontMm = 0.35,
  flatRearMm = 0.35,
  samples = 12,
} = {}) {
  const length = Math.max(0.1, Number(lengthMm) || 0.1);
  const front = Math.max(0.2, Number(frontDiameterMm) || 0.2);
  const rear = Math.max(0.2, Number(rearDiameterMm) || front);
  const frontFlat = clampNumber(flatFrontMm, 0, length * 0.35, 0);
  const rearFlat = clampNumber(flatRearMm, 0, length * 0.35, 0);
  const transitionStart = frontFlat / length;
  const transitionEnd = Math.max(
    transitionStart,
    Math.min(1, (length - rearFlat) / length)
  );
  if (Math.abs(front - rear) < 1e-9 || transitionEnd <= transitionStart + 1e-9) {
    return [[0, front], [1, rear]];
  }
  const count = Math.max(4, Math.min(32, Math.round(Number(samples) || 12)));
  const points = [[0, front]];
  if (transitionStart > 0) points.push([transitionStart, front]);
  for (let index = 1; index < count; index += 1) {
    const t = index / count;
    const u = transitionStart + (transitionEnd - transitionStart) * t;
    points.push([u, front + (rear - front) * smoothstep01(t)]);
  }
  points.push([transitionEnd, rear]);
  if (transitionEnd < 1) points.push([1, rear]);
  return points;
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
