import assert from 'node:assert/strict';
import { resolveBarrelRearSeam, rotatePointAroundPivot } from '../src/geometry.js';

const seam = resolveBarrelRearSeam({
  barrelDiameterMm: 6.5,
  rearDiameterMm: 5.2,
  barrelRearCoverage: 0.80,
  rearFrontCoverage: 0.46,
  targetVisibleDiameterMm: 5.2,
});
assert.ok(seam.visibleDiameterMm > 0);
assert.equal(seam.visibleDiameterMm, 5.2);
// Mesh envelopes may be wider than the physical diameter because transparent source-image
// padding must not make the visible shaft/barrel artificially thin.
assert.ok(seam.barrelEndEnvelopeMm > 0);
assert.ok(seam.rearStartEnvelopeMm > 0);
assert.ok(seam.visibleDeltaMm < 1e-10, `visible seam mismatch ${seam.visibleDeltaMm}`);
assert.ok(Math.abs(seam.barrelVisibleAtJoinMm - 5.2) < 1e-10);
assert.ok(Math.abs(seam.rearVisibleAtJoinMm - 5.2) < 1e-10);

const pivot = { x: 0, y: 212 };
for (const angle of [-75, -30, 0, 30, 75]) {
  const rotatedPivot = rotatePointAroundPivot(pivot, angle, pivot);
  assert.ok(Math.hypot(rotatedPivot.x - pivot.x, rotatedPivot.y - pivot.y) < 1e-10);
}
const p = rotatePointAroundPivot({ x: 100, y: 212 }, 90, pivot);
assert.ok(Math.abs(p.x) < 1e-9);
assert.ok(Math.abs(p.y - 312) < 1e-9);
console.log('PASS: barrel/rear visible seam is equalized to rear nominal diameter and screen rotation preserves the tip pivot');
