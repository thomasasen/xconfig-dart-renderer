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
  const requestedTarget = Number(targetVisibleDiameterMm);
  const visibleDiameterMm = Number.isFinite(requestedTarget) && requestedTarget > 0
    ? requestedTarget
    : Math.min(leftDiameter, rightDiameter);
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
    visibleDeltaMm: Math.abs(leftEnvelopeMm * lCoverage - rightEnvelopeMm * rCoverage),
  };
}

export function resolveBarrelRearSeam({
  barrelDiameterMm,
  rearDiameterMm,
  barrelRearCoverage = 1,
  rearFrontCoverage = 1,
  targetVisibleDiameterMm = null,
} = {}) {
  const rearDiameter = Math.max(0.2, Number(rearDiameterMm) || 0.2);
  const join = resolveVisibleJoin({
    leftNominalDiameterMm: barrelDiameterMm,
    rightNominalDiameterMm: rearDiameter,
    leftCoverage: barrelRearCoverage,
    rightCoverage: rearFrontCoverage,
    targetVisibleDiameterMm: targetVisibleDiameterMm ?? rearDiameter,
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
  samples = 10,
} = {}) {
  const length = Math.max(0.1, Number(lengthMm) || 0.1);
  const front = Math.max(0.2, Number(frontDiameterMm) || 0.2);
  const rear = Math.max(0.2, Number(rearDiameterMm) || front);
  const frontFlat = clampNumber(flatFrontMm, 0, length * 0.35, 0.35);
  const rearFlat = clampNumber(flatRearMm, 0, length * 0.35, 0.35);
  const usable = Math.max(1e-6, length - frontFlat - rearFlat);
  const count = Math.max(4, Math.min(32, Math.round(Number(samples) || 10)));
  const points = [[0, front]];
  if (frontFlat > 0) points.push([frontFlat / length, front]);
  for (let i = 1; i < count; i += 1) {
    const t = i / count;
    const u = (frontFlat + usable * t) / length;
    const diameter = front + (rear - front) * smoothstep01(t);
    points.push([u, diameter]);
  }
  if (rearFlat > 0) points.push([(length - rearFlat) / length, rear]);
  points.push([1, rear]);
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

const FLIGHT_AXIS_EPSILON = 1e-9;

function clipFlightProfileToAxisHalf(profile, keepPositive) {
  const points = (Array.isArray(profile) ? profile : [])
    .map((point) => [Number(point?.[0]), Number(point?.[1])])
    .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
  if (points.length < 3) return [];

  const inside = ([, y]) => keepPositive
    ? y >= -FLIGHT_AXIS_EPSILON
    : y <= FLIGHT_AXIS_EPSILON;
  const output = [];

  const intersection = (a, b) => {
    const dy = b[1] - a[1];
    if (Math.abs(dy) < FLIGHT_AXIS_EPSILON) return [b[0], 0];
    const t = -a[1] / dy;
    return [a[0] + (b[0] - a[0]) * t, 0];
  };

  for (let index = 0; index < points.length; index += 1) {
    const current = points[index];
    const next = points[(index + 1) % points.length];
    const currentInside = inside(current);
    const nextInside = inside(next);

    if (currentInside && nextInside) {
      output.push(next);
    } else if (currentInside && !nextInside) {
      output.push(intersection(current, next));
    } else if (!currentInside && nextInside) {
      output.push(intersection(current, next), next);
    }
  }

  const deduped = [];
  for (const [x, y] of output) {
    const point = [x, Math.abs(y) < FLIGHT_AXIS_EPSILON ? 0 : y];
    const previous = deduped[deduped.length - 1];
    if (
      previous &&
      Math.abs(previous[0] - point[0]) < FLIGHT_AXIS_EPSILON &&
      Math.abs(previous[1] - point[1]) < FLIGHT_AXIS_EPSILON
    ) continue;
    deduped.push(point);
  }
  if (
    deduped.length > 2 &&
    Math.abs(deduped[0][0] - deduped[deduped.length - 1][0]) < FLIGHT_AXIS_EPSILON &&
    Math.abs(deduped[0][1] - deduped[deduped.length - 1][1]) < FLIGHT_AXIS_EPSILON
  ) deduped.pop();

  return deduped;
}

/**
 * Split one canonical flight plane on the dart axis.
 *
 * Two complete transparent planes cross each other, so no whole-plane painter order can
 * be correct. Splitting both planes on their physical intersection line creates four
 * half-fins. Any pair then only shares the axis boundary and can be ordered back-to-front
 * as a complete transparent surface.
 */
export function splitFlightProfile(profile) {
  const fallback = [[0, 0], [.25, 1], [1, .8], [1, -.8], [.25, -1]];
  const source = Array.isArray(profile) && profile.length >= 3 ? profile : fallback;
  const positive = clipFlightProfileToAxisHalf(source, true);
  const negative = clipFlightProfileToAxisHalf(source, false);
  if (positive.length < 3 || negative.length < 3) {
    throw new Error('flight profile must cross the dart axis and produce two valid half-fins');
  }
  return { positive, negative };
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
