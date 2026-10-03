import { loadCatalog, resolveAssembly } from './catalog.js';
import {
  validateAssembly,
  pointFitsBarrel,
  rearFitsBarrel,
  shaftFitsBarrel,
  flightFitsShaft,
  firstCompatible,
} from './compatibility.js';
import {
  SharedDartComponentRenderer,
  XCONFIG_SPRITE_CONTRACT,
} from './renderer.js';
import { selectionFromPreset, overwriteSelection } from './builder-state.js';
import { rotatePointAroundPivot } from './geometry.js';

const $ = (id) => document.getElementById(id);
const status = $('status');
const evidenceBox = $('evidence');
const warnings = $('warnings');
const assemblyJson = $('assemblyJson');

let catalog;
let renderer;
let currentPresetId = '';
let dirty = false;
let renderEpoch = 0;
let scheduledFrame = 0;
const posedScratch = document.createElement('canvas');

const selection = {
  pointId: '',
  barrelId: '',
  shaftId: '',
  flightId: '',
  rearSystemId: '',
};

function setStatus(text, kind = '') {
  status.textContent = text;
  status.className = kind;
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));
}

function statusChip(statusValue) {
  return `<span class="evidence-chip ev-${statusValue.toLowerCase()}">${esc(statusValue)}</span>`;
}

function evidenceHtml(component) {
  if (!component) return '<em>nicht aktiv</em>';
  const rows = (component.evidence || []).map((entry) =>
    `<li>${statusChip(entry.status)} ${esc(entry.note)}${entry.source
      ? ` <a href="${esc(entry.source)}" target="_blank" rel="noreferrer">Quelle</a>`
      : ''}</li>`
  ).join('');
  return `<strong>${esc(component.name)}</strong><ul>${rows || '<li>keine Evidence-Metadaten</li>'}</ul>`;
}

function componentGroups() {
  return [
    ['point', 'Point'],
    ['barrel', 'Barrel'],
    ['rearSystem', 'Rear-System'],
    ['shaft', 'Shaft'],
    ['flight', 'Flight'],
  ];
}

function fillSelect(element, dictionary, selectedId, predicate = () => true, noneLabel = null) {
  const keep = selectedId;
  element.replaceChildren();
  if (noneLabel !== null) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = noneLabel;
    element.append(option);
  }
  for (const component of Object.values(dictionary || {})) {
    const option = document.createElement('option');
    option.value = component.id;
    option.textContent = component.name;
    option.disabled = !predicate(component);
    element.append(option);
  }
  element.value = keep;
}

function ensureCompatible() {
  let assembly = resolveAssembly(catalog, selection);
  if (!assembly.barrel) return;

  if (!pointFitsBarrel(assembly.point, assembly.barrel)) {
    const point = firstCompatible(
      catalog.components.points,
      (candidate) => pointFitsBarrel(candidate, assembly.barrel)
    );
    selection.pointId = point?.id || '';
  }

  if (selection.rearSystemId) {
    assembly = resolveAssembly(catalog, selection);
    if (!rearFitsBarrel(assembly.rearSystem, assembly.barrel)) {
      selection.rearSystemId = '';
    }
  }

  if (!selection.rearSystemId) {
    assembly = resolveAssembly(catalog, selection);
    if (!shaftFitsBarrel(assembly.shaft, assembly.barrel)) {
      const shaft = firstCompatible(
        catalog.components.shafts,
        (candidate) => shaftFitsBarrel(candidate, assembly.barrel)
      );
      selection.shaftId = shaft?.id || '';
    }
    assembly = resolveAssembly(catalog, selection);
    if (!flightFitsShaft(assembly.flight, assembly.shaft)) {
      const flight = firstCompatible(
        catalog.components.flights,
        (candidate) => flightFitsShaft(candidate, assembly.shaft)
      );
      selection.flightId = flight?.id || '';
    }
  }
}

function refreshSelects() {
  ensureCompatible();
  const assembly = resolveAssembly(catalog, selection);
  const barrel = assembly.barrel;

  fillSelect(
    $('point'),
    catalog.components.points,
    selection.pointId,
    (point) => !barrel || pointFitsBarrel(point, barrel)
  );
  fillSelect(
    $('barrel'),
    catalog.components.barrels,
    selection.barrelId,
    (candidateBarrel) => {
      const point = catalog.components.points[selection.pointId];
      return !point || pointFitsBarrel(point, candidateBarrel);
    }
  );
  fillSelect(
    $('rear'),
    catalog.components.rearSystems,
    selection.rearSystemId,
    (rear) => !barrel || rearFitsBarrel(rear, barrel),
    '— klassisch: separater Shaft + Flight —'
  );

  const integrated = Boolean(selection.rearSystemId);
  fillSelect(
    $('shaft'),
    catalog.components.shafts,
    selection.shaftId,
    (shaft) => !barrel || shaftFitsBarrel(shaft, barrel)
  );
  const shaft = catalog.components.shafts[selection.shaftId];
  fillSelect(
    $('flight'),
    catalog.components.flights,
    selection.flightId,
    (flight) => !shaft || flightFitsShaft(flight, shaft)
  );

  $('shaft').disabled = integrated;
  $('flight').disabled = integrated;
  $('rearLock').textContent = integrated
    ? 'Integriertes Rear-System aktiv: separate Shaft-/Flight-Auswahl ist gesperrt.'
    : 'Klassischer Aufbau: Shaft und Flight sind getrennte Komponenten.';
}

function presetPose(preset = catalog?.presets?.[currentPresetId]) {
  return {
    screenRotationDeg: Number(preset?.defaultPose?.screenRotationDeg ?? 0),
    incidenceDeg: Number(preset?.defaultPose?.incidenceDeg ?? 35),
    rollDeg: Number(preset?.defaultPose?.rollDeg ?? 0),
  };
}

function applyPoseToControls(pose) {
  $('screenRotation').value = pose.screenRotationDeg;
  $('incidence').value = pose.incidenceDeg;
  $('roll').value = pose.rollDeg;
  updatePoseOutputs();
}

function updatePoseOutputs() {
  $('screenOut').textContent = `${Number($('screenRotation').value)}°`;
  $('incOut').textContent = `${Number($('incidence').value)}°`;
  $('rollOut').textContent = `${Number($('roll').value)}°`;
}

function applyPreset(id) {
  const preset = catalog.presets[id];
  if (!preset) return;
  currentPresetId = id;
  dirty = false;
  overwriteSelection(selection, selectionFromPreset(preset));
  applyPoseToControls(presetPose(preset));
  refreshSelects();
  updateSource(preset);
  scheduleRender();
}

function resetPose() {
  applyPoseToControls(presetPose());
  scheduleRender();
}

function updateSource(preset = catalog.presets[currentPresetId]) {
  const sourceImage = $('sourceImage');
  const localFallback = preset?.sourceImage || '';
  const remoteReference = preset?.referenceImageUrl || '';
  sourceImage.onerror = null;
  if (remoteReference) {
    sourceImage.onerror = () => {
      sourceImage.onerror = null;
      sourceImage.src = localFallback;
    };
    sourceImage.src = remoteReference;
  } else {
    sourceImage.src = localFallback;
  }
  const caption = $('sourceCaption');
  caption.replaceChildren();
  if (!preset) {
    caption.textContent = 'Kein Preset';
    return;
  }

  if (remoteReference) {
    caption.append(document.createTextNode(
      `${preset.name} · recherchiertes externes Produktfoto · lokaler Fallback: WEB-REFERENCED RECONSTRUCTION`
    ));
  } else {
    const label = preset.sourceLabel || 'supplied source';
    caption.append(document.createTextNode(`${preset.name} · ${label}`));
  }
  if (preset.sourcePage) {
    const link = document.createElement('a');
    link.href = preset.sourcePage;
    link.target = '_blank';
    link.rel = 'noreferrer noopener';
    link.textContent = ' Produktseite ↗';
    caption.append(document.createTextNode(' · '));
    caption.append(link);
  }
}

function safeRollRange(assembly) {
  const tail = assembly.rearSystem || assembly.flight;
  if (!tail) return [-15, 15];
  return [
    Number(tail.safeRollMinDeg ?? -20),
    Number(tail.safeRollMaxDeg ?? 20),
  ];
}

/**
 * Builder-only preview of xConfig's external rotateGroup. The 3D renderer stays
 * canonical/horizontal; this second canvas rotates the finished sprite around its
 * exact logical tip without feeding screen rotation back into 3D geometry.
 */
function drawScreenRotatedPreview(sourceCanvas, targetCanvas, screenRotationDeg) {
  const targetWidth = 1000;
  const targetHeight = 800;
  targetCanvas.width = targetWidth;
  targetCanvas.height = targetHeight;

  const ctx = targetCanvas.getContext('2d', { alpha: true });
  ctx.clearRect(0, 0, targetWidth, targetHeight);

  const angle = Number(screenRotationDeg) || 0;
  const pivot = XCONFIG_SPRITE_CONTRACT.tip;
  const sourceCorners = [
    { x: 0, y: 0 },
    { x: XCONFIG_SPRITE_CONTRACT.width, y: 0 },
    { x: XCONFIG_SPRITE_CONTRACT.width, y: XCONFIG_SPRITE_CONTRACT.height },
    { x: 0, y: XCONFIG_SPRITE_CONTRACT.height },
  ].map((point) => rotatePointAroundPivot(point, angle, pivot));

  const relCorners = sourceCorners.map((point) => ({
    x: point.x - pivot.x,
    y: point.y - pivot.y,
  }));
  const minX = Math.min(...relCorners.map((point) => point.x));
  const maxX = Math.max(...relCorners.map((point) => point.x));
  const minY = Math.min(...relCorners.map((point) => point.y));
  const maxY = Math.max(...relCorners.map((point) => point.y));
  const margin = 44;
  const scale = Math.min(
    1,
    (targetWidth - margin * 2) / Math.max(1, maxX - minX),
    (targetHeight - margin * 2) / Math.max(1, maxY - minY)
  );
  const previewTip = {
    x: margin - minX * scale,
    y: margin - minY * scale,
  };

  ctx.save();
  ctx.translate(previewTip.x, previewTip.y);
  ctx.rotate(angle * Math.PI / 180);
  ctx.scale(scale, scale);
  ctx.drawImage(sourceCanvas, -pivot.x, -pivot.y);
  ctx.restore();

  ctx.save();
  ctx.strokeStyle = '#f2c76e';
  ctx.fillStyle = '#f2c76e';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(previewTip.x, previewTip.y, 5, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(previewTip.x - 10, previewTip.y);
  ctx.lineTo(previewTip.x + 10, previewTip.y);
  ctx.moveTo(previewTip.x, previewTip.y - 10);
  ctx.lineTo(previewTip.x, previewTip.y + 10);
  ctx.stroke();
  ctx.font = '12px ui-monospace, monospace';
  ctx.fillText('TIP', previewTip.x + 9, previewTip.y - 9);
  ctx.restore();

  const rotatedTip = rotatePointAroundPivot(pivot, angle, pivot);
  const pivotDriftPx = Math.hypot(rotatedTip.x - pivot.x, rotatedTip.y - pivot.y);
  return {
    screenRotationDeg: angle,
    previewScale: scale,
    previewTip,
    pivotDriftPx,
  };
}

function updateEvidence(assembly, validation, renderMeta) {
  evidenceBox.innerHTML = componentGroups().map(([key, label]) =>
    `<section><h3>${label}</h3>${evidenceHtml(assembly[key])}</section>`
  ).join('');

  const [rollMin, rollMax] = safeRollRange(assembly);
  const roll = Number($('roll').value);
  const incidence = Number($('incidence').value);
  const screenRotation = Number($('screenRotation').value);
  const rollSafe = roll >= rollMin && roll <= rollMax;
  const warningList = [];

  if (!validation.valid) warningList.push(...validation.errors);
  if (!rollSafe) {
    warningList.push(
      `Roll ${roll}° liegt außerhalb des source-grounded/konservativen Bereichs ${rollMin}…${rollMax}°. Plane B ist als APPROXIMATED gekennzeichnet.`
    );
  }
  const jointDelta = Number(renderMeta?.posed?.jointMetrics?.visibleDeltaMm);
  if (Number.isFinite(jointDelta) && jointDelta > 0.03) {
    warningList.push(
      `Barrel/Shaft-Naht weicht noch um ${jointDelta.toFixed(2)} mm sichtbare Dicke ab.`
    );
  }

  const preset = catalog.presets[currentPresetId];
  if (dirty) {
    warningList.push(
      `Assembly wurde gegenüber Preset ${preset?.name || currentPresetId} manuell verändert. „Preset zurücksetzen“ stellt es vollständig wieder her.`
    );
  }
  if (preset?.notes?.length) warningList.push(...preset.notes);

  warnings.innerHTML = warningList.length
    ? warningList.map((item) => `<li>${esc(item)}</li>`).join('')
    : '<li>Keine aktuelle Kompatibilitätsverletzung.</li>';

  const payload = {
    selection: { ...selection },
    valid: validation.valid,
    pose: {
      screenRotationDeg: screenRotation,
      incidenceDeg: incidence,
      rollDeg: roll,
    },
    safeRoll: [rollMin, rollMax],
    renderer: renderMeta,
    contract: XCONFIG_SPRITE_CONTRACT,
  };
  assemblyJson.textContent = JSON.stringify(payload, null, 2);
  $('rollPolicy').textContent =
    `Safe Roll: ${rollMin}° … ${rollMax}° · aktuell ${roll}° → ${rollSafe
      ? 'SOURCE-GROUNDED/konservativ'
      : 'APPROXIMATED'}`;
}

async function renderAll() {
  const epoch = ++renderEpoch;
  try {
    refreshSelects();
    updatePoseOutputs();
    const assembly = resolveAssembly(catalog, selection);
    const validation = validateAssembly(assembly);
    if (!validation.valid) {
      updateEvidence(assembly, validation, null);
      return;
    }

    setStatus('baue Assembly…');
    await renderer.setAssembly(assembly);
    if (epoch !== renderEpoch) return;

    const screenRotation = Number($('screenRotation').value);
    const incidence = Number($('incidence').value);
    const roll = Number($('roll').value);

    const orthogonal = renderer.renderToSprite({
      incidenceDeg: 0,
      rollDeg: 0,
      targetCanvas: $('orthogonal'),
    });
    const posed = renderer.renderToSprite({
      incidenceDeg: incidence,
      rollDeg: roll,
      targetCanvas: posedScratch,
    });
    const screenPreview = drawScreenRotatedPreview(
      posedScratch,
      $('posed'),
      screenRotation
    );

    if (epoch !== renderEpoch) return;
    const renderMeta = {
      orthogonal: {
        tipDriftPx: orthogonal.tipDriftPx,
        axisYErrorPx: orthogonal.canonicalAxisYErrorPx,
        jointMetrics: orthogonal.jointMetrics,
        jointSprite: orthogonal.jointSprite,
      },
      posed: {
        tipDriftPx: posed.tipDriftPx,
        axisYErrorPx: posed.canonicalAxisYErrorPx,
        axis: posed.axis,
        flightFacing: posed.flightFacing,
        jointMetrics: posed.jointMetrics,
        jointSprite: posed.jointSprite,
      },
      screenPreview,
      flightPlaneModel: posed.flightPlaneModel,
    };

    updateEvidence(assembly, validation, renderMeta);
    setStatus(`ready · ${renderer.threeSource}`, 'ok');
    window.__POC_READY__ = true;
    window.__POC_LAST_RENDER__ = {
      presetId: currentPresetId,
      selection: { ...selection },
      validation,
      pose: { screenRotationDeg: screenRotation, incidenceDeg: incidence, rollDeg: roll },
      ortho: {
        tipDriftPx: orthogonal.tipDriftPx,
        jointMetrics: orthogonal.jointMetrics,
        jointSprite: orthogonal.jointSprite,
      },
      posed: {
        tipDriftPx: posed.tipDriftPx,
        flightFacing: posed.flightFacing,
        jointMetrics: posed.jointMetrics,
        jointSprite: posed.jointSprite,
      },
      screenPreview,
    };
  } catch (error) {
    if (epoch !== renderEpoch) return;
    setStatus('FEHLER', 'bad');
    warnings.innerHTML = `<li>${esc(error.stack || error.message || error)}</li>`;
    console.error(error);
  }
}

function scheduleRender() {
  if (scheduledFrame) cancelAnimationFrame(scheduledFrame);
  updatePoseOutputs();
  scheduledFrame = requestAnimationFrame(() => {
    scheduledFrame = 0;
    renderAll();
  });
}

async function benchmark() {
  const assembly = resolveAssembly(catalog, selection);
  const validation = validateAssembly(assembly);
  if (!validation.valid) return;
  $('benchOut').textContent = 'läuft…';
  await renderer.setAssembly(assembly);
  $('benchOut').textContent = JSON.stringify(await renderer.benchmark(), null, 2);
}

async function renderGallery() {
  const box = $('gallery');
  box.replaceChildren();
  const assembly = resolveAssembly(catalog, selection);
  await renderer.setAssembly(assembly);
  const currentScreen = Number($('screenRotation').value);
  const poses = [
    { incidenceDeg: 15, rollDeg: -25, screenRotationDeg: currentScreen - 20 },
    { incidenceDeg: 30, rollDeg: 0, screenRotationDeg: currentScreen },
    { incidenceDeg: 45, rollDeg: 25, screenRotationDeg: currentScreen + 20 },
    { incidenceDeg: 60, rollDeg: -15, screenRotationDeg: currentScreen },
  ];

  for (const pose of poses) {
    const raw = document.createElement('canvas');
    const result = renderer.renderToSprite({
      incidenceDeg: pose.incidenceDeg,
      rollDeg: pose.rollDeg,
      targetCanvas: raw,
    });
    const canvas = document.createElement('canvas');
    const preview = drawScreenRotatedPreview(raw, canvas, pose.screenRotationDeg);
    const figure = document.createElement('figure');
    const caption = document.createElement('figcaption');
    caption.textContent =
      `Screen ${pose.screenRotationDeg}° · Incidence ${pose.incidenceDeg}° · Roll ${pose.rollDeg}° · Tip drift ${result.tipDriftPx.toExponential(1)} px / external pivot ${preview.pivotDriftPx.toExponential(1)} px`;
    figure.append(canvas, caption);
    box.append(figure);
    await new Promise(requestAnimationFrame);
  }
}

function bind() {
  $('preset').onchange = (event) => applyPreset(event.target.value);
  $('reset').onclick = () => applyPreset(currentPresetId);
  $('poseReset').onclick = resetPose;

  for (const [id, key] of [
    ['point', 'pointId'],
    ['barrel', 'barrelId'],
    ['shaft', 'shaftId'],
    ['flight', 'flightId'],
    ['rear', 'rearSystemId'],
  ]) {
    $(id).onchange = (event) => {
      selection[key] = event.target.value;
      dirty = true;
      scheduleRender();
    };
  }

  $('screenRotation').oninput = scheduleRender;
  $('incidence').oninput = scheduleRender;
  $('roll').oninput = scheduleRender;
  $('galleryBtn').onclick = renderGallery;
  $('bench').onclick = benchmark;
  $('contextLoss').onclick = () => {
    $('benchOut').textContent = JSON.stringify(renderer.simulateContextLoss(), null, 2);
  };
}

try {
  setStatus('lade Katalog…');
  catalog = await loadCatalog();
  fillSelect($('preset'), catalog.presets, '', () => true, '— Preset wählen —');
  renderer = await new SharedDartComponentRenderer({
    onStatus: (message) => setStatus(
      message,
      message.startsWith('ready') ? 'ok' : message.includes('lost') ? 'warn' : ''
    ),
  }).init();
  bind();
  applyPreset('prodigy-23');

  window.__CATALOG__ = catalog;
  window.__RENDERER__ = renderer;
  window.__SELECTION__ = selection;
  window.__APP_API__ = {
    applyPreset,
    renderAll,
    resolveAssembly: () => resolveAssembly(catalog, selection),
    setPose: ({ screenRotationDeg, incidenceDeg, rollDeg } = {}) => {
      if (screenRotationDeg !== undefined) $('screenRotation').value = screenRotationDeg;
      if (incidenceDeg !== undefined) $('incidence').value = incidenceDeg;
      if (rollDeg !== undefined) $('roll').value = rollDeg;
      return renderAll();
    },
  };
} catch (error) {
  setStatus('FEHLER', 'bad');
  warnings.innerHTML = `<li>${esc(error.stack || error.message || error)}</li>`;
  console.error(error);
}
