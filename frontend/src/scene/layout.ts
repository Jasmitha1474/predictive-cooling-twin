import * as THREE from 'three';

// Physical layout of the virtual hall. Rack/GPU ids come from the backend "hello" message,
// so the hall follows whatever layout the backend runs (default 4 racks x 5 GPUs).

export const RACK = { w: 1.1, h: 2.5, d: 1.3 };
export const NODE = { w: 0.95, h: 0.3, d: 1.15, y0: 0.45, dy: 0.4 };
export const CDU_POS = new THREE.Vector3(0, 0, 9.5);
export const CONTROL_ROOM_POS = new THREE.Vector3(0, 0, -15);

export interface RackLayout {
  id: string;
  pos: THREE.Vector3;
  side: 1 | -1; // which side the pipes come in from (towards the centre aisle)
  gpus: string[];
}

export function buildLayout(layout: { gpu_id: string; rack: string }[]): RackLayout[] {
  const racks = [...new Set(layout.map((l) => l.rack))].sort();
  const rows = Math.ceil(racks.length / 2);
  return racks.map((id, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = col === 0 ? -3.5 : 3.5;
    const z = (row - (rows - 1) / 2) * 6;
    return {
      id,
      pos: new THREE.Vector3(x, 0, z),
      side: (col === 0 ? 1 : -1) as 1 | -1,
      gpus: layout.filter((l) => l.rack === id).map((l) => l.gpu_id).sort(),
    };
  });
}

export function nodePosition(rack: RackLayout, gpuId: string): THREE.Vector3 {
  const i = rack.gpus.indexOf(gpuId);
  return new THREE.Vector3(rack.pos.x, NODE.y0 + i * NODE.dy, rack.pos.z);
}

/** Supply (CDU -> rack) and return (rack -> CDU) pipe centre-lines for one rack. */
export function pipeCurves(rack: RackLayout) {
  const s = rack.side;
  const xa = rack.pos.x + s * (RACK.w / 2 + 0.25); // riser next to the rack, aisle side
  const sup = new THREE.CatmullRomCurve3(
    [
      new THREE.Vector3(CDU_POS.x - 0.35, 0.55, CDU_POS.z - 0.9),
      new THREE.Vector3(-0.35, 0.18, CDU_POS.z - 2.2),
      new THREE.Vector3(-0.35 * s, 0.18, rack.pos.z + 0.25),
      new THREE.Vector3(xa, 0.18, rack.pos.z + 0.25),
      new THREE.Vector3(xa, 2.3, rack.pos.z + 0.25),
    ],
    false,
    'catmullrom',
    0.05,
  );
  const ret = new THREE.CatmullRomCurve3(
    [
      new THREE.Vector3(xa, 2.3, rack.pos.z - 0.25),
      new THREE.Vector3(xa, 0.3, rack.pos.z - 0.25),
      new THREE.Vector3(0.35 * s, 0.3, rack.pos.z - 0.25),
      new THREE.Vector3(0.35, 0.3, CDU_POS.z - 2.2),
      new THREE.Vector3(CDU_POS.x + 0.35, 0.55, CDU_POS.z - 0.9),
    ],
    false,
    'catmullrom',
    0.05,
  );
  return { sup, ret };
}

export function valvePosition(rack: RackLayout) {
  // on the supply branch, in the aisle just before the riser
  return new THREE.Vector3(rack.pos.x + rack.side * (RACK.w / 2 + 1.1), 0.18, rack.pos.z + 0.25);
}
