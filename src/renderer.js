import { buildSmoothBridgeProfile, buildSmoothJoinProfile, profileEndpointSlope, resolveBarrelRearSeam, resolveVisibleJoin, splitFlightProfile } from './geometry.js';

let THREE = null;
const THREE_VERSION = '0.180.0';
const LOCAL_THREE_URL = '../node_modules/three/build/three.module.js';
const CDN_THREE_URL = `https://cdn.jsdelivr.net/npm/three@${THREE_VERSION}/build/three.module.js`;

export const XCONFIG_SPRITE_CONTRACT = Object.freeze({
  width: 789,
  height: 331,
  tip: { x: 0, y: 212 },
});

const FIN_AZIMUTH_DEG = Object.freeze([0, 90, 180, 270]);

const FIN_LAYOUT = Object.freeze([
  { key: 'A-positive', half: 'positive', plane: 'A', azimuthDeg: 0, defaultFrontSide: 'FRONT' },
  { key: 'B-positive', half: 'positive', plane: 'B', azimuthDeg: 90, defaultFrontSide: 'FRONT' },
  { key: 'A-negative', half: 'negative', plane: 'A', azimuthDeg: 180, defaultFrontSide: 'BACK' },
  { key: 'B-negative', half: 'negative', plane: 'B', azimuthDeg: 270, defaultFrontSide: 'BACK' },
]);

function canonicalRadialFinProfile(profile) {
  const raw = Array.isArray(profile) ? profile : [];
  const points = [];
  for (const pair of raw) {
    const x = Number(pair?.[0]);
    const y = Math.abs(Number(pair?.[1]));
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    const point = [x, y < 1e-9 ? 0 : y];
    const previous = points[points.length - 1];
    if (
      previous &&
      Math.abs(previous[0] - point[0]) < 1e-9 &&
      Math.abs(previous[1] - point[1]) < 1e-9
    ) continue;
    points.push(point);
  }
  if (
    points.length > 2 &&
    Math.abs(points[0][0] - points[points.length - 1][0]) < 1e-9 &&
    Math.abs(points[0][1] - points[points.length - 1][1]) < 1e-9
  ) points.pop();
  if (points.length < 3) {
    throw new Error('flight half-fin must produce a valid radial contour');
  }
  return points;
}

function deg(value) {
  return Number(value) * Math.PI / 180;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, Number(value) || 0));
}

function withTimeout(promise, ms, message) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(message)), ms)),
  ]);
}

async function loadThree(onStatus = () => {}) {
  if (THREE) return { module: THREE, source: 'cached' };

  let localError;
  try {
    onStatus('lade Three.js lokal…');
    THREE = await import(LOCAL_THREE_URL);
    return { module: THREE, source: 'local node_modules' };
  } catch (error) {
    localError = error;
  }

  try {
    onStatus('lokales Three.js fehlt · CDN fallback…');
    THREE = await withTimeout(import(CDN_THREE_URL), 8000, 'CDN timeout');
    return { module: THREE, source: 'jsDelivr CDN' };
  } catch (error) {
    throw new Error(
      `Three.js load failed. Local: ${localError?.message}; CDN: ${error?.message}`
    );
  }
}

function canvasToBlob(canvas) {
  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('toBlob null'))),
      'image/png'
    )
  );
}

/**
 * Textured 2D ribbon with local diameter changes. This lets the barrel keep its
 * source-supported body diameter while tapering only near the rear connection.
 */
function makeProfiledRibbonGeometry(x0, x1, diameterProfile) {
  const length = Math.max(0.001, x1 - x0);
  const raw = Array.isArray(diameterProfile) && diameterProfile.length
    ? diameterProfile
    : [[0, 2], [1, 2]];

  const sections = raw
    .map(([u, diameter]) => [clamp(u, 0, 1), Math.max(0.1, Number(diameter) || 0.1)])
    .sort((a, b) => a[0] - b[0]);

  const deduped = [];
  for (const section of sections) {
    if (deduped.length && Math.abs(deduped[deduped.length - 1][0] - section[0]) < 1e-6) {
      deduped[deduped.length - 1] = section;
    } else {
      deduped.push(section);
    }
  }
  if (deduped[0][0] > 0) deduped.unshift([0, deduped[0][1]]);
  if (deduped[deduped.length - 1][0] < 1) {
    deduped.push([1, deduped[deduped.length - 1][1]]);
  }

  const positions = [];
  const uvs = [];
  for (let index = 0; index < deduped.length - 1; index += 1) {
    const [u0, d0] = deduped[index];
    const [u1, d1] = deduped[index + 1];
    const xa = x0 + u0 * length;
    const xb = x0 + u1 * length;
    const ya = d0 / 2;
    const yb = d1 / 2;

    positions.push(
      xa, -ya, 0,
      xb, -yb, 0,
      xb, yb, 0,
      xa, -ya, 0,
      xb, yb, 0,
      xa, ya, 0
    );
    uvs.push(
      u0, 1,
      u1, 1,
      u1, 0,
      u0, 1,
      u1, 0,
      u0, 0
    );
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    'position',
    new THREE.BufferAttribute(new Float32Array(positions), 3)
  );
  geometry.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(uvs), 2));
  return geometry;
}

function bodyProfile({
  bodyDiameterMm,
  frontDiameterMm = bodyDiameterMm,
  rearDiameterMm = bodyDiameterMm,
  lengthMm,
  frontBlendMm = 0,
  rearBlendMm = 0,
}) {
  const length = Math.max(0.1, Number(lengthMm) || 0.1);
  const body = Math.max(0.2, Number(bodyDiameterMm) || 0.2);
  const front = Math.max(0.2, Number(frontDiameterMm) || body);
  const rear = Math.max(0.2, Number(rearDiameterMm) || body);
  const frontU = clamp((Number(frontBlendMm) || 0) / length, 0, 0.45);
  const rearU = 1 - clamp((Number(rearBlendMm) || 0) / length, 0, 0.45);

  return [
    [0, front],
    [frontU, body],
    [Math.max(frontU, rearU), body],
    [1, rear],
  ];
}

function makeFlightGeometry(
  profile,
  root,
  length,
  radius,
  { halfTexture = false, vAtAxis = 0.5 } = {}
) {
  const points = Array.isArray(profile) && profile.length >= 3
    ? profile
    : [[0, 0], [.25, 1], [1, .8], [1, -.8], [.25, -1]];
  const shape = new THREE.Shape();
  points.forEach(([xn, yn], index) => {
    const x = root + Number(xn) * length;
    const y = Number(yn) * radius;
    if (index === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  });
  shape.closePath();

  const geometry = new THREE.ShapeGeometry(shape);
  const position = geometry.getAttribute('position');
  const uv = new Float32Array(position.count * 2);
  const axisV = clamp(vAtAxis, 0, 1);
  for (let index = 0; index < position.count; index += 1) {
    const x = position.getX(index);
    const y = position.getY(index);
    uv[index * 2] = clamp((x - root) / length, 0, 1);
    if (halfTexture) {
      const radial = clamp(Math.abs(y) / Math.max(.0001, radius), 0, 1);
      uv[index * 2 + 1] = clamp(
        axisV + (1 - 2 * axisV) * radial,
        0,
        1
      );
    } else {
      // Legacy whole-plane texture: each physical half samples its corresponding
      // half of the original full-height canonical texture.
      uv[index * 2 + 1] = clamp(.5 - y / (2 * radius), 0, 1);
    }
  }
  geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  geometry.computeBoundingSphere();
  return geometry;
}

function texturePromise(loader, url) {
  return new Promise((resolve, reject) => loader.load(url, resolve, undefined, reject));
}

export class SharedDartComponentRenderer {
  constructor({ renderWidth = 1800, renderHeight = 620, onStatus = () => {} } = {}) {
    this.renderWidth = renderWidth;
    this.renderHeight = renderHeight;
    this.onStatus = onStatus;
    this.textureCache = new Map();
    this.edgeCoverageCache = new Map();
    this.spriteCache = new Map();
    this.invalid = false;
    this.contextLossCount = 0;
    this.contextRestoreCount = 0;
    this.assembly = null;
    this.assemblyKey = '';
    this.jointMetrics = null;
    this.assemblyGeneration = 0;
  }

  async init() {
    const loaded = await loadThree(this.onStatus);
    this.threeSource = loaded.source;
    this.X_AXIS = new THREE.Vector3(1, 0, 0);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(
      2.63,
      this.renderWidth / this.renderHeight,
      1,
      10000
    );
    this.camera.position.set(0, 0, 3500);
    this.camera.lookAt(0, 0, 0);
    this.camera.updateMatrixWorld(true);

    this.root = new THREE.Group();
    this.scene.add(this.root);

    this.hiddenHost = document.createElement('div');
    this.hiddenHost.style.cssText =
      'position:fixed;left:-10000px;top:-10000px;width:1px;height:1px;overflow:hidden';
    document.body.appendChild(this.hiddenHost);
    this.#createRenderer();
    this.onStatus(`ready · Three.js ${this.threeSource}`);
    return this;
  }

  #createRenderer() {
    if (this.renderer) {
      try { this.renderer.dispose(); } catch {}
      this.renderer.domElement.remove();
    }
    this.renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      premultipliedAlpha: false,
      preserveDrawingBuffer: true,
      powerPreference: 'high-performance',
    });
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(this.renderWidth, this.renderHeight, false);
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.renderer.domElement.addEventListener('webglcontextlost', (event) => {
      event.preventDefault();
      this.contextLossCount += 1;
      this.invalid = true;
      this.spriteCache.clear();
      this.onStatus('context-lost · renderer invalid');
    });
    this.renderer.domElement.addEventListener('webglcontextrestored', () => {
      this.contextRestoreCount += 1;
      this.spriteCache.clear();
      for (const texture of this.textureCache.values()) texture.needsUpdate = true;
      this.invalid = false;
      this.onStatus('context-restored · resources flagged');
      setTimeout(() => this.#createRenderer(), 0);
    });
    this.hiddenHost.appendChild(this.renderer.domElement);
  }

  async #texture(url) {
    if (this.textureCache.has(url)) return this.textureCache.get(url);
    const loader = new THREE.TextureLoader();
    const texture = await texturePromise(loader, url);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.generateMipmaps = false;
    this.textureCache.set(url, texture);
    return texture;
  }

  #mat(texture, { flight = false, side = THREE.DoubleSide } = {}) {
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      alphaTest: .018,
      depthTest: true,
      depthWrite: !flight,
      side,
      toneMapped: false,
    });
    material.forceSinglePass = true;
    return material;
  }

  #measureEdgeCoverage(texture, side) {
    const cacheKey = `${texture.uuid}|${side}|join-band-v2`;
    if (this.edgeCoverageCache.has(cacheKey)) {
      return this.edgeCoverageCache.get(cacheKey);
    }

    const image = texture?.image;
    const width = Number(image?.naturalWidth || image?.videoWidth || image?.width || 0);
    const height = Number(image?.naturalHeight || image?.videoHeight || image?.height || 0);
    if (!(width > 0) || !(height > 0)) {
      this.edgeCoverageCache.set(cacheKey, 1);
      return 1;
    }

    try {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(image, 0, 0, width, height);
      const data = ctx.getImageData(0, 0, width, height).data;

      // Do not use the literal first/last pixel columns as a physical connector gauge.
      // Product-image extracts often contain bevels, anti-aliasing, shadow or transparent
      // padding there. Measure a short internal band close to the connection and use its
      // median visible alpha span instead.
      const sampleCount = Math.max(5, Math.min(13, Math.round(width * 0.06)));
      const bandStart = side === 'right' ? 0.86 : 0.04;
      const bandEnd = side === 'right' ? 0.96 : 0.14;
      const spans = [];

      for (let sample = 0; sample < sampleCount; sample += 1) {
        const t = sampleCount === 1 ? 0.5 : sample / (sampleCount - 1);
        const u = bandStart + (bandEnd - bandStart) * t;
        const x = Math.min(width - 1, Math.max(0, Math.round(u * (width - 1))));
        let minY = height;
        let maxY = -1;
        for (let y = 0; y < height; y += 1) {
          const alpha = data[(y * width + x) * 4 + 3];
          if (alpha >= 28) {
            minY = Math.min(minY, y);
            maxY = Math.max(maxY, y);
          }
        }
        if (maxY >= minY) spans.push((maxY - minY + 1) / height);
      }

      spans.sort((a, b) => a - b);
      const coverage = spans.length
        ? spans[Math.floor(spans.length / 2)]
        : 1;
      const safeCoverage = clamp(coverage, 0.15, 1);
      this.edgeCoverageCache.set(cacheKey, safeCoverage);
      return safeCoverage;
    } catch {
      this.edgeCoverageCache.set(cacheKey, 1);
      return 1;
    }
  }

  #measureBodyCoverage(texture) {
    const cacheKey = `${texture.uuid}|body`;
    if (this.edgeCoverageCache.has(cacheKey)) {
      return this.edgeCoverageCache.get(cacheKey);
    }
    const image = texture?.image;
    const width = Number(image?.naturalWidth || image?.videoWidth || image?.width || 0);
    const height = Number(image?.naturalHeight || image?.videoHeight || image?.height || 0);
    if (!(width > 0) || !(height > 0)) {
      this.edgeCoverageCache.set(cacheKey, 1);
      return 1;
    }
    try {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(image, 0, 0, width, height);
      const data = ctx.getImageData(0, 0, width, height).data;
      const spans = [];
      const sampleCount = 17;
      for (let sample = 0; sample < sampleCount; sample += 1) {
        const u = .08 + (.84 * sample / Math.max(1, sampleCount - 1));
        const x = Math.min(width - 1, Math.max(0, Math.round(u * (width - 1))));
        let minY = height;
        let maxY = -1;
        for (let y = 0; y < height; y += 1) {
          const alpha = data[(y * width + x) * 4 + 3];
          if (alpha >= 28) {
            minY = Math.min(minY, y);
            maxY = Math.max(maxY, y);
          }
        }
        if (maxY >= minY) spans.push((maxY - minY + 1) / height);
      }
      spans.sort((a, b) => a - b);
      const coverage = spans.length ? spans[Math.floor(spans.length / 2)] : 1;
      const safeCoverage = clamp(coverage, 0.15, 1);
      this.edgeCoverageCache.set(cacheKey, safeCoverage);
      return safeCoverage;
    } catch {
      this.edgeCoverageCache.set(cacheKey, 1);
      return 1;
    }
  }

  #clearScene() {
    const all = [];
    this.root.traverse((object) => {
      if (object !== this.root) all.push(object);
    });
    for (const object of all) {
      object.geometry?.dispose?.();
      if (Array.isArray(object.material)) object.material.forEach((m) => m.dispose?.());
      else object.material?.dispose?.();
    }
    this.root.clear();
  }

  async setAssembly(assembly) {
    const nextKey = [
      assembly.point?.id,
      assembly.barrel?.id,
      assembly.rearSystem?.id || '',
      assembly.shaft?.id || '',
      assembly.flight?.id || '',
    ].join('|');
    if (this.assembly && nextKey === this.assemblyKey) return this;

    const generation = ++this.assemblyGeneration;
    this.assembly = assembly;
    this.assemblyKey = nextKey;
    this.spriteCache.clear();
    this.#clearScene();

    const rearObject = assembly.rearSystem || assembly.shaft;
    const rearLength = assembly.rearSystem
      ? assembly.rearSystem.renderShaftLengthMm
      : assembly.shaft?.renderLengthMm;
    const rearDiameter = assembly.rearSystem
      ? assembly.rearSystem.renderShaftDiameterMm
      : assembly.shaft?.renderDiameterMm || 4.8;
    const rearTextureUrl = assembly.rearSystem
      ? assembly.rearSystem.shaftTexture
      : assembly.shaft?.texture;
    const rootTextureUrl = assembly.rearSystem?.rootTexture || null;

    const pointTexture = await this.#texture(assembly.point?.texture);
    const barrelTexture = await this.#texture(assembly.barrel?.texture);
    const rearTexture = await this.#texture(rearTextureUrl);
    const rootTexture = rootTextureUrl ? await this.#texture(rootTextureUrl) : null;
    if (generation !== this.assemblyGeneration) return this;

    const barrelRearCoverage = this.#measureEdgeCoverage(barrelTexture, 'right');
    const rearFrontCoverage = this.#measureEdgeCoverage(rearTexture, 'left');
    const rearBackCoverage = this.#measureEdgeCoverage(rearTexture, 'right');
    const rootFrontCoverage = rootTexture ? this.#measureEdgeCoverage(rootTexture, 'left') : 1;
    const rootBackCoverage = rootTexture ? this.#measureEdgeCoverage(rootTexture, 'right') : 1;
    const barrelBodyCoverage = this.#measureBodyCoverage(barrelTexture);
    const rearBodyCoverage = this.#measureBodyCoverage(rearTexture);

    const pointLength = Math.max(.1, Number(assembly.point?.renderLengthMm) || 1);
    const barrelLength = Math.max(.1, Number(assembly.barrel?.renderLengthMm) || 1);
    const rearLengthSafe = Math.max(.1, Number(rearLength) || 1);
    const pointDiameter = Math.max(.2, Number(assembly.point?.renderDiameterMm) || 2);
    const barrelDiameter = Math.max(.2, Number(assembly.barrel?.renderDiameterMm) || 2);
    const rearDiameterSafe = Math.max(.2, Number(rearDiameter) || 2);
    const rootLengthSafe = rootTexture
      ? Math.max(.1, Number(assembly.rearSystem?.renderRootLengthMm) || 2.5)
      : 0;
    const rootFrontDiameter = rootTexture
      ? Math.max(.2, Number(assembly.rearSystem?.renderRootFrontDiameterMm) || rearDiameterSafe)
      : rearDiameterSafe;
    const rootRearDiameter = rootTexture
      ? Math.max(.2, Number(assembly.rearSystem?.renderRootRearDiameterMm) || rootFrontDiameter)
      : rootFrontDiameter;
    this.barrelRearJoinX = pointLength + barrelLength;

    const seam = resolveBarrelRearSeam({
      barrelDiameterMm: barrelDiameter,
      rearDiameterMm: rearDiameterSafe,
      barrelRearCoverage,
      rearFrontCoverage,
      targetVisibleDiameterMm: rearDiameterSafe,
    });
    const barrelBodyEnvelopeMm = barrelDiameter / Math.max(.15, barrelBodyCoverage);
    const rearBodyEnvelopeMm = rearDiameterSafe / Math.max(.15, rearBodyCoverage);
    const barrelProfile = buildSmoothJoinProfile({
      bodyDiameterMm: barrelBodyEnvelopeMm,
      joinDiameterMm: seam.barrelEndEnvelopeMm,
      lengthMm: barrelLength,
      side: 'rear',
      transitionMm: Math.min(3.2, barrelLength * 0.09),
      flatJoinMm: Math.min(1.2, barrelLength * 0.035),
      samples: 10,
    });
    const rearProfile = buildSmoothJoinProfile({
      bodyDiameterMm: rearBodyEnvelopeMm,
      joinDiameterMm: seam.rearStartEnvelopeMm,
      lengthMm: rearLengthSafe,
      side: 'front',
      transitionMm: Math.min(2.8, rearLengthSafe * 0.12),
      flatJoinMm: Math.min(1.2, rearLengthSafe * 0.05),
      samples: 10,
    });
    const barrelJoinSlope = profileEndpointSlope(barrelProfile, barrelLength, 'rear');
    const rearJoinSlope = profileEndpointSlope(rearProfile, rearLengthSafe, 'front');

    let shaftRootSeam = null;
    let rootProfile = null;
    if (rootTexture) {
      shaftRootSeam = resolveVisibleJoin({
        leftNominalDiameterMm: rearDiameterSafe,
        rightNominalDiameterMm: rootFrontDiameter,
        leftCoverage: rearBackCoverage,
        rightCoverage: rootFrontCoverage,
        targetVisibleDiameterMm: rearDiameterSafe,
      });
      const rootFrontEnvelope = shaftRootSeam.rightEnvelopeMm;
      const rootRearEnvelope = rootRearDiameter / Math.max(.15, rootBackCoverage);
      rootProfile = buildSmoothBridgeProfile({
        frontDiameterMm: rootFrontEnvelope,
        rearDiameterMm: rootRearEnvelope,
        lengthMm: rootLengthSafe,
        flatFrontMm: Math.min(.5, rootLengthSafe * .18),
        flatRearMm: Math.min(.5, rootLengthSafe * .18),
        samples: 12,
      });
    }

    this.jointMetrics = {
      ...seam,
      barrelBodyCoverage,
      rearBodyCoverage,
      barrelBodyEnvelopeMm,
      rearBodyEnvelopeMm,
      barrelJoinSlopeMmPerMm: barrelJoinSlope,
      rearJoinSlopeMmPerMm: rearJoinSlope,
      joinSlopeDeltaMmPerMm: Math.abs(barrelJoinSlope - rearJoinSlope),
      barrelId: assembly.barrel?.id,
      rearId: rearObject?.id,
      shaftRootVisibleDeltaMm: Number(shaftRootSeam?.visibleDeltaMm || 0),
      rootPresent: Boolean(rootTexture),
      rootLengthMm: rootLengthSafe,
      rootFrontDiameterMm: rootFrontDiameter,
      rootRearDiameterMm: rootRearDiameter,
      policy: rootTexture
        ? 'BARREL_SHAFT_VISIBLE_JOIN + SHAFT_ROOT_VISIBLE_JOIN + SMOOTH_ROOT_BRIDGE'
        : 'INTERNAL_ALPHA_BAND + SMOOTHSTEP + FLAT_TANGENT_JOIN',
    };

    let x = 0;
    this.bodyMeshes = [];

    const bodyDefinitions = [
      {
        name: 'point',
        length: pointLength,
        texture: pointTexture,
        profile: bodyProfile({
          bodyDiameterMm: pointDiameter,
          lengthMm: pointLength,
        }),
      },
      {
        name: 'barrel',
        length: barrelLength,
        texture: barrelTexture,
        profile: barrelProfile,
      },
      {
        name: assembly.rearSystem ? 'rear-shaft-core' : 'shaft',
        length: rearLengthSafe,
        texture: rearTexture,
        profile: rearProfile,
      },
    ];
    if (rootTexture && rootProfile) {
      bodyDefinitions.push({
        name: 'rear-root',
        length: rootLengthSafe,
        texture: rootTexture,
        profile: rootProfile,
      });
    }

    for (const definition of bodyDefinitions) {
      const geometry = makeProfiledRibbonGeometry(
        x,
        x + definition.length,
        definition.profile
      );
      const mesh = new THREE.Mesh(geometry, this.#mat(definition.texture));
      mesh.name = `body-${definition.name}`;
      mesh.renderOrder = 10;
      this.root.add(mesh);
      this.bodyMeshes.push(mesh);
      x += definition.length;
    }

    const tail = assembly.rearSystem || assembly.flight;
    const flightLength = Number(tail.renderFlightLengthMm || tail.renderLengthMm || 42);
    const flightRadius = Number(tail.renderFlightRadiusMm || tail.renderRadiusMm || 18);
    const flightRootOverlapMm = Number(tail.flightRootOverlapMm ?? 1.5);
    const flightRoot = x - flightRootOverlapMm;
    const halfProfiles = splitFlightProfile(tail.planeProfile);

    this.flightGroup = new THREE.Group();
    this.flightGroup.name = 'flight-four-half-fin-cross';
    this.root.add(this.flightGroup);

    const planeATexture = await this.#texture(tail.planeATexture);
    const planeBTexture = await this.#texture(tail.planeBTexture || tail.planeATexture);
    if (generation !== this.assemblyGeneration) return this;

    this.flightFins = [];
    this.flightSurfaceMeshes = [];
    this.planeMeshes = [];

    for (let stableIndex = 0; stableIndex < FIN_LAYOUT.length; stableIndex += 1) {
      const definition = FIN_LAYOUT[stableIndex];
      const sourceHalfProfile = definition.half === 'positive'
        ? halfProfiles.positive
        : halfProfiles.negative;
      const radialProfile = canonicalRadialFinProfile(sourceHalfProfile);
      const authoredFace = tail.finTextures?.[definition.key] || null;
      const halfTexture = Boolean(authoredFace);
      const vAtAxis = Number(authoredFace?.vAtAxis ?? .5);
      const authoredFrontSide = String(
        authoredFace?.frontSide || definition.defaultFrontSide
      ).toUpperCase();
      const frontSide = authoredFrontSide === 'BACK'
        ? THREE.BackSide
        : THREE.FrontSide;
      const backSide = authoredFrontSide === 'BACK'
        ? THREE.FrontSide
        : THREE.BackSide;

      // Product photography supplies appearance evidence, not flight geometry. Each
      // physical fin therefore uses canonical radial geometry. Source samples are bound
      // only to the explicitly calibrated face side; unseen faces stay approximated.
      const defaultFrontUrl = definition.plane === 'A'
        ? tail.planeATexture
        : (tail.planeBTexture || tail.planeATexture);
      const frontUrl = authoredFace?.front || defaultFrontUrl;
      const backUrl = authoredFace?.back || tail.planeBTexture || tail.planeATexture;
      const frontTexture = frontUrl === tail.planeATexture
        ? planeATexture
        : frontUrl === tail.planeBTexture
          ? planeBTexture
          : await this.#texture(frontUrl);
      const backTexture = backUrl === tail.planeATexture
        ? planeATexture
        : backUrl === tail.planeBTexture
          ? planeBTexture
          : await this.#texture(backUrl);
      if (generation !== this.assemblyGeneration) return this;

      const frontGeometry = makeFlightGeometry(
        radialProfile,
        flightRoot,
        flightLength,
        flightRadius,
        { halfTexture, vAtAxis }
      );
      const backGeometry = frontGeometry.clone();

      const frontMesh = new THREE.Mesh(
        frontGeometry,
        this.#mat(frontTexture, { flight: true, side: frontSide })
      );
      frontMesh.rotation.x = deg(definition.azimuthDeg);
      frontMesh.name = `flight-fin-${definition.key}-front`;

      const backMesh = new THREE.Mesh(
        backGeometry,
        this.#mat(backTexture, { flight: true, side: backSide })
      );
      backMesh.rotation.x = deg(definition.azimuthDeg);
      backMesh.name = `flight-fin-${definition.key}-back`;

      for (const mesh of [frontMesh, backMesh]) {
        mesh.userData.flightPlane = definition.plane;
        mesh.userData.flightHalf = definition.half;
        mesh.userData.flightAzimuthDeg = definition.azimuthDeg;
        mesh.userData.flightStableIndex = stableIndex;
        this.flightGroup.add(mesh);
        this.flightSurfaceMeshes.push(mesh);
      }

      frontMesh.userData.flightFace = 'front';
      backMesh.userData.flightFace = 'back';

      const fin = {
        key: definition.key,
        plane: definition.plane,
        half: definition.half,
        azimuthDeg: definition.azimuthDeg,
        stableIndex,
        frontMesh,
        backMesh,
        frontUrl,
        backUrl,
        frontSide: authoredFrontSide,
        frontProvenance: authoredFace?.frontProvenance
          || (definition.plane === 'A' ? tail.planeAProvenance : tail.planeBProvenance)
          || 'UNKNOWN',
        backProvenance: authoredFace?.backProvenance
          || tail.planeBProvenance
          || 'APPROXIMATED',
        halfTexture,
        vAtAxis,
      };
      this.flightFins.push(fin);
      this.planeMeshes.push(frontMesh);
    }

    this.flightSpineMesh = null;
    this.flightSpineMeta = null;
    const spine = tail.finFaceAuthoring?.spineMaterial;
    if (assembly.rearSystem && spine) {
      const colorRgb = Array.isArray(spine.colorRgb) ? spine.colorRgb : [128, 128, 128];
      const diameterMm = Math.max(.35, Number(spine.diameterMm || 1.0));
      const opacity = clamp(Number(spine.opacity ?? .9), .1, 1);
      const geometry = new THREE.CylinderGeometry(
        diameterMm / 2,
        diameterMm / 2,
        flightLength,
        12,
        1,
        false
      );
      geometry.rotateZ(-Math.PI / 2);
      geometry.translate(flightRoot + flightLength / 2, 0, 0);
      const material = new THREE.MeshBasicMaterial({
        color: new THREE.Color(
          clamp(Number(colorRgb[0] || 0) / 255, 0, 1),
          clamp(Number(colorRgb[1] || 0) / 255, 0, 1),
          clamp(Number(colorRgb[2] || 0) / 255, 0, 1)
        ),
        transparent: opacity < .999,
        opacity,
        depthTest: true,
        depthWrite: true,
        side: THREE.DoubleSide,
        toneMapped: false,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.name = 'flight-integrated-axis-spine';
      mesh.renderOrder = 40;
      this.flightGroup.add(mesh);
      this.flightSpineMesh = mesh;
      this.flightSpineMeta = {
        present: true,
        diameterMm,
        opacity,
        colorRgb: colorRgb.map((value) => Number(value)),
        provenance: spine.provenance || 'APPROXIMATED',
        diameterProvenance: spine.diameterProvenance || 'HEURISTIC',
      };
    }

    this.totalLength = x + flightLength;
    this.scene.updateMatrixWorld(true);
    return this;
  }

  axisForIncidence(incidenceDeg) {
    const incidence = deg(clamp(incidenceDeg, 0, 89.5));
    return new THREE.Vector3(
      Math.cos(incidence),
      0,
      Math.sin(incidence)
    ).normalize();
  }

  #updateFlightOrder() {
    if (!this.flightFins?.length) return;
    this.scene.updateMatrixWorld(true);
    this.camera.updateMatrixWorld(true);
    const ranked = this.flightFins.map((fin) => {
      const mesh = fin.frontMesh;
      mesh.geometry.computeBoundingSphere();
      const center = mesh.geometry.boundingSphere.center.clone().applyMatrix4(mesh.matrixWorld);
      const cameraCenter = center.clone().applyMatrix4(this.camera.matrixWorldInverse);
      const normal = new THREE.Vector3(0, 0, 1)
        .applyQuaternion(mesh.getWorldQuaternion(new THREE.Quaternion()))
        .normalize();
      const facing = Math.abs(normal.z);
      // Both face meshes describe one physical half-fin. Hide/order them together.
      const visible = facing > 1e-4;
      fin.frontMesh.visible = visible;
      fin.backMesh.visible = visible;
      const cameraDepth = -cameraCenter.z;
      fin.cameraDepth = cameraDepth;
      fin.frontMesh.userData.cameraDepth = cameraDepth;
      fin.backMesh.userData.cameraDepth = cameraDepth;
      return {
        fin,
        cameraDepth,
        stableIndex: fin.stableIndex,
      };
    });

    // Physical half-fins meet only at the dart axis, so their painter order is valid.
    // Front/back surface meshes of one fin share the same order; side culling guarantees
    // that only the physically visible face contributes fragments.
    ranked.sort((a, b) =>
      (b.cameraDepth - a.cameraDepth) ||
      (a.stableIndex - b.stableIndex)
    );
    ranked.forEach(({ fin }, index) => {
      const order = 20 + index;
      fin.frontMesh.renderOrder = order;
      fin.backMesh.renderOrder = order;
    });
  }

  applyPose({ incidenceDeg = 35, rollDeg = 0 } = {}) {
    const axis = this.axisForIncidence(incidenceDeg);
    this.root.quaternion.setFromUnitVectors(this.X_AXIS, axis);
    this.flightGroup.rotation.x = deg(Number(rollDeg) || 0);
    this.scene.updateMatrixWorld(true);
    this.#updateFlightOrder();
    return axis;
  }

  projectWorld(world) {
    const value = world.clone().project(this.camera);
    return {
      x: (value.x * .5 + .5) * this.renderWidth,
      y: (-value.y * .5 + .5) * this.renderHeight,
    };
  }

  tipMapping() {
    const source = this.projectWorld(new THREE.Vector3(0, 0, 0));
    return {
      source,
      target: { ...XCONFIG_SPRITE_CONTRACT.tip },
      offset: {
        x: -source.x,
        y: XCONFIG_SPRITE_CONTRACT.tip.y - source.y,
      },
    };
  }

  #flightFacing() {
    if (!this.planeMeshes?.length) return [];
    return this.planeMeshes.map((mesh) => {
      const normal = new THREE.Vector3(0, 0, 1)
        .applyQuaternion(mesh.getWorldQuaternion(new THREE.Quaternion()))
        .normalize();
      return Number(Math.abs(normal.z).toFixed(4));
    });
  }

  renderToSprite({ incidenceDeg = 35, rollDeg = 0, targetCanvas = null } = {}) {
    if (this.invalid) throw new Error('renderer invalid after WebGL context loss');
    if (!this.assembly) throw new Error('assembly not set');

    const axis = this.applyPose({ incidenceDeg, rollDeg });
    this.renderer.clear();
    this.renderer.render(this.scene, this.camera);

    const canvas = targetCanvas || document.createElement('canvas');
    canvas.width = XCONFIG_SPRITE_CONTRACT.width;
    canvas.height = XCONFIG_SPRITE_CONTRACT.height;
    const ctx = canvas.getContext('2d', { alpha: true });
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const mapping = this.tipMapping();
    ctx.drawImage(this.renderer.domElement, mapping.offset.x, mapping.offset.y);

    const jointWorld = new THREE.Vector3(this.barrelRearJoinX || 0, 0, 0)
      .applyQuaternion(this.root.quaternion);
    const jointProjected = this.projectWorld(jointWorld);
    const jointSprite = {
      x: jointProjected.x + mapping.offset.x,
      y: jointProjected.y + mapping.offset.y,
    };

    const tipDrift = Math.hypot(
      mapping.source.x + mapping.offset.x,
      mapping.source.y + mapping.offset.y - XCONFIG_SPRITE_CONTRACT.tip.y
    );
    const tailWorld = new THREE.Vector3(this.totalLength, 0, 0)
      .applyQuaternion(this.root.quaternion);
    const tail = this.projectWorld(tailWorld);
    const axisYError =
      tail.y + mapping.offset.y - XCONFIG_SPRITE_CONTRACT.tip.y;

    return {
      canvas,
      axis: axis.toArray(),
      tipDriftPx: tipDrift,
      canonicalAxisYErrorPx: axisYError,
      contract: XCONFIG_SPRITE_CONTRACT,
      flightPlaneModel: 'FOUR_EXPLICIT_RADIAL_FINS_0_90_180_270_WITH_SEPARATE_FACE_SURFACES',
      flightMeshCount: this.planeMeshes?.length || 0,
      flightSurfaceMeshCount: this.flightSurfaceMeshes?.length || 0,
      flightFacing: this.#flightFacing(),
      flightSpine: this.flightSpineMeta || { present: false },
      flightRenderOrder: (this.flightFins || []).map((fin) => ({
        name: fin.key,
        plane: fin.plane,
        half: fin.half,
        azimuthDeg: fin.azimuthDeg,
        frontSide: fin.frontSide,
        cameraDepth: Number(fin.cameraDepth || 0),
        renderOrder: fin.frontMesh.renderOrder,
        visible: fin.frontMesh.visible,
        frontTexture: fin.frontUrl,
        backTexture: fin.backUrl,
        frontProvenance: fin.frontProvenance,
        backProvenance: fin.backProvenance,
        halfTexture: fin.halfTexture,
      })),
      jointSprite,
      jointMetrics: this.jointMetrics,
    };
  }

  cacheKey({ incidenceDeg = 35, rollDeg = 0, quality = 'builder' } = {}) {
    return `${this.assemblyKey}|i${Math.round(incidenceDeg * 2) / 2}|r${Math.round(rollDeg * 2) / 2}|${quality}`;
  }

  async renderCached(options = {}) {
    const key = this.cacheKey(options);
    if (this.spriteCache.has(key)) {
      return { key, cacheHit: true, bitmap: this.spriteCache.get(key) };
    }
    const { canvas } = this.renderToSprite(options);
    const bitmap = await createImageBitmap(canvas);
    this.spriteCache.set(key, bitmap);
    return { key, cacheHit: false, bitmap };
  }

  drawBitmap(canvas, bitmap) {
    canvas.width = XCONFIG_SPRITE_CONTRACT.width;
    canvas.height = XCONFIG_SPRITE_CONTRACT.height;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0);
  }

  selfTest() {
    let maxTip = 0;
    let maxAxis = 0;
    const flightFacingSamples = [];
    for (const incidenceDeg of [0, 20, 35, 50]) {
      for (const rollDeg of [-45, -20, 0, 20, 45]) {
        const result = this.renderToSprite({ incidenceDeg, rollDeg });
        maxTip = Math.max(maxTip, result.tipDriftPx);
        maxAxis = Math.max(maxAxis, Math.abs(result.canonicalAxisYErrorPx));
        flightFacingSamples.push({ incidenceDeg, rollDeg, facing: result.flightFacing });
      }
    }
    return {
      passed:
        maxTip < 1e-8 &&
        maxAxis < 1e-5 &&
        Number(this.jointMetrics?.visibleDeltaMm || 0) < 1e-8 &&
        Number(this.jointMetrics?.shaftRootVisibleDeltaMm || 0) < 1e-8 &&
        Number(this.jointMetrics?.joinSlopeDeltaMmPerMm || 0) < 1e-8 &&
        this.planeMeshes?.length === 4 &&
        this.flightSurfaceMeshes?.length === 8 &&
        this.flightFins?.every((fin, index) => fin.azimuthDeg === FIN_AZIMUTH_DEG[index]) &&
        (!this.assembly?.rearSystem?.finFaceAuthoring?.spineMaterial || Boolean(this.flightSpineMesh)),
      maxTipDriftPx: maxTip,
      maxCanonicalAxisYErrorPx: maxAxis,
      jointVisibleDeltaMm: Number(this.jointMetrics?.visibleDeltaMm || 0),
      jointSlopeDeltaMmPerMm: Number(this.jointMetrics?.joinSlopeDeltaMmPerMm || 0),
      shaftRootVisibleDeltaMm: Number(this.jointMetrics?.shaftRootVisibleDeltaMm || 0),
      rootPresent: Boolean(this.jointMetrics?.rootPresent),
      finAzimuthDeg: [...FIN_AZIMUTH_DEG],
      flightMeshCount: this.planeMeshes?.length || 0,
      flightSurfaceMeshCount: this.flightSurfaceMeshes?.length || 0,
      flightSpine: this.flightSpineMeta || { present: false },
      flightTopology: 'FOUR_EXPLICIT_RADIAL_FINS_0_90_180_270_WITH_SEPARATE_FACE_SURFACES',
      flightFacingSamples,
    };
  }

  async benchmark() {
    this.spriteCache.clear();
    const poses = [
      { incidenceDeg: 20, rollDeg: -10 },
      { incidenceDeg: 35, rollDeg: 0 },
      { incidenceDeg: 45, rollDeg: 15 },
    ];
    const miss = [];
    for (const pose of poses) {
      const started = performance.now();
      await this.renderCached(pose);
      miss.push(performance.now() - started);
    }
    const hitStarted = performance.now();
    await this.renderCached(poses[0]);
    const hit = performance.now() - hitStarted;
    const { canvas } = this.renderToSprite(poses[1]);
    const encodeStarted = performance.now();
    const blob = await canvasToBlob(canvas);
    return {
      threeSource: this.threeSource,
      missMs: miss,
      hitMs: hit,
      pngEncodeMs: performance.now() - encodeStarted,
      pngBytes: blob.size,
      cacheEntries: this.spriteCache.size,
      jointMetrics: this.jointMetrics,
      selfTest: this.selfTest(),
    };
  }

  contextStats() {
    return {
      lost: this.contextLossCount,
      restored: this.contextRestoreCount,
      invalid: this.invalid,
    };
  }

  simulateContextLoss() {
    const gl = this.renderer.getContext();
    const extension = gl.getExtension('WEBGL_lose_context');
    if (!extension) return { supported: false, ...this.contextStats() };
    extension.loseContext();
    setTimeout(() => extension.restoreContext(), 350);
    return { supported: true, ...this.contextStats() };
  }
}
