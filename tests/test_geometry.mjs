import assert from 'node:assert/strict';
import { buildSmoothBridgeProfile, buildSmoothJoinProfile, profileEndpointSlope, resolveBarrelRearSeam, resolveVisibleJoin, rotatePointAroundPivot } from '../src/geometry.js';

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

const seamCases = [
  { name: 'Clemens G2 classic shaft', barrel: 6.9, rear: 4.8, barrelCoverage: .82, rearCoverage: .62 },
  { name: 'Clemens 95K integrated rear', barrel: 6.9, rear: 5.2, barrelCoverage: .84, rearCoverage: .74 },
  { name: 'thin barrel', barrel: 6.1, rear: 4.8, barrelCoverage: .90, rearCoverage: .70 },
  { name: 'thick barrel', barrel: 7.8, rear: 5.2, barrelCoverage: .78, rearCoverage: .68 },
];

for (const c of seamCases) {
  const s = resolveBarrelRearSeam({
    barrelDiameterMm: c.barrel,
    rearDiameterMm: c.rear,
    barrelRearCoverage: c.barrelCoverage,
    rearFrontCoverage: c.rearCoverage,
    targetVisibleDiameterMm: c.rear,
  });
  const barrelProfile = buildSmoothJoinProfile({
    bodyDiameterMm: c.barrel / c.barrelCoverage,
    joinDiameterMm: s.barrelEndEnvelopeMm,
    lengthMm: 52,
    side: 'rear',
    transitionMm: 3.2,
    flatJoinMm: 1.2,
  });
  const rearProfile = buildSmoothJoinProfile({
    bodyDiameterMm: c.rear / c.rearCoverage,
    joinDiameterMm: s.rearStartEnvelopeMm,
    lengthMm: 30,
    side: 'front',
    transitionMm: 2.8,
    flatJoinMm: 1.2,
  });
  const barrelSlope = profileEndpointSlope(barrelProfile, 52, 'rear');
  const rearSlope = profileEndpointSlope(rearProfile, 30, 'front');
  assert.ok(Math.abs(barrelSlope) < 1e-10, `${c.name}: barrel join slope ${barrelSlope}`);
  assert.ok(Math.abs(rearSlope) < 1e-10, `${c.name}: rear join slope ${rearSlope}`);
  assert.ok(Math.abs(barrelSlope - rearSlope) < 1e-10, `${c.name}: join slope mismatch`);
}

const alreadyMatched = buildSmoothJoinProfile({
  bodyDiameterMm: 5.2,
  joinDiameterMm: 5.2,
  lengthMm: 20,
  side: 'front',
});
assert.deepEqual(alreadyMatched, [[0, 5.2], [1, 5.2]], 'matching connector diameters must not create an artificial taper');



const genericJoin = resolveVisibleJoin({
  leftNominalDiameterMm: 4.8,
  rightNominalDiameterMm: 4.8,
  leftCoverage: .72,
  rightCoverage: .64,
  targetVisibleDiameterMm: 4.8,
});
assert.ok(genericJoin.visibleDeltaMm < 1e-10, `generic join visible mismatch ${genericJoin.visibleDeltaMm}`);

const rootBridge = buildSmoothBridgeProfile({
  frontDiameterMm: 4.8,
  rearDiameterMm: 6.2,
  lengthMm: 2.5,
  flatFrontMm: .4,
  flatRearMm: .4,
  samples: 12,
});
assert.ok(rootBridge.length >= 8);
assert.equal(rootBridge[0][1], 4.8);
assert.equal(rootBridge[rootBridge.length - 1][1], 6.2);
assert.ok(Math.abs(profileEndpointSlope(rootBridge, 2.5, 'front')) < 1e-10, 'root front tangent must be flat');
assert.ok(Math.abs(profileEndpointSlope(rootBridge, 2.5, 'rear')) < 1e-10, 'root rear tangent must be flat');
for (let i = 1; i < rootBridge.length; i += 1) {
  assert.ok(rootBridge[i][1] + 1e-10 >= rootBridge[i - 1][1], 'root bridge must not pinch while widening');
}

const pivot = { x: 0, y: 212 };
for (const angle of [-75, -30, 0, 30, 75]) {
  const rotatedPivot = rotatePointAroundPivot(pivot, angle, pivot);
  assert.ok(Math.hypot(rotatedPivot.x - pivot.x, rotatedPivot.y - pivot.y) < 1e-10);
}
const p = rotatePointAroundPivot({ x: 100, y: 212 }, 90, pivot);
assert.ok(Math.abs(p.x) < 1e-9);
assert.ok(Math.abs(p.y - 312) < 1e-9);
console.log('PASS: seam/root thickness and tangent continuity hold; screen rotation preserves the tip pivot');
