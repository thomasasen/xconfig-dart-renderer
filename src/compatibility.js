export function pointFitsBarrel(point, barrel) {
  return Boolean(point && barrel && point.interface === barrel.pointInterface);
}
export function rearFitsBarrel(rear, barrel) {
  return Boolean(rear && barrel && rear.rearThread === barrel.rearThread);
}
export function shaftFitsBarrel(shaft, barrel) {
  return Boolean(shaft && barrel && shaft.rearThread === barrel.rearThread);
}
export function flightFitsShaft(flight, shaft) {
  return Boolean(flight && shaft && flight.flightMount === shaft.flightMount);
}

export function validateAssembly(assembly) {
  const errors=[];
  const {point,barrel,rearSystem,shaft,flight}=assembly;
  if (!point) errors.push('Point fehlt.');
  if (!barrel) errors.push('Barrel fehlt.');
  if (point && barrel && !pointFitsBarrel(point,barrel)) errors.push(`Point ${point.interface} passt nicht zu Barrel ${barrel.pointInterface}.`);
  if (rearSystem) {
    if (!rearFitsBarrel(rearSystem,barrel)) errors.push(`Rear-System ${rearSystem.rearThread} passt nicht zu Barrel ${barrel.rearThread}.`);
    if (shaft || flight) errors.push('Integriertes Rear-System darf nicht parallel zu separatem Shaft/Flight aktiv sein.');
  } else {
    if (!shaft) errors.push('Shaft fehlt.');
    if (!flight) errors.push('Flight fehlt.');
    if (shaft && barrel && !shaftFitsBarrel(shaft,barrel)) errors.push(`Shaft ${shaft.rearThread} passt nicht zu Barrel ${barrel.rearThread}.`);
    if (flight && shaft && !flightFitsShaft(flight,shaft)) errors.push(`Flight ${flight.flightMount} passt nicht zu Shaft ${shaft.flightMount}.`);
  }
  return {valid:errors.length===0,errors};
}

export function firstCompatible(dict, predicate) {
  return Object.values(dict || {}).find(predicate) || null;
}
