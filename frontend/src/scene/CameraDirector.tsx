import { OrbitControls } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { useTelemetry } from '../telemetry/store';
import { CDU_POS, CONTROL_ROOM_POS, RACK, nodePosition, valvePosition, type RackLayout } from './layout';

type Shot = { pos: THREE.Vector3; target: THREE.Vector3 };

/**
 * Named views with smooth transitions, plus the event sequence of brief section 42.
 * The sequence is started ONLY by a backend `thermal_event_predicted` and each step advances
 * when the backend data show the corresponding change (valve command issued, valve reached
 * command, temperature trend levelled), with a time cap so the camera never stalls.
 */
export function CameraDirector({ racks }: { racks: RackLayout[] }) {
  const controls = useRef<any>(null);
  const { camera } = useThree();
  const goal = useRef<Shot | null>(null);
  const seq = useRef<{ gpu: string; step: number; t: number; v0: number } | null>(null);
  const internal = useRef(false); // true while the event sequence itself changes view/selection

  const shotFor = (view: string, rackId?: string | null, gpu?: string | null): Shot => {
    const rack = racks.find((r) => r.id === rackId) ?? racks.find((r) => gpu && r.gpus.includes(gpu));
    switch (view) {
      case 'rack':
        if (rack) return { pos: rack.pos.clone().add(new THREE.Vector3(rack.side * 2.2, 2.6, 5.6)), target: rack.pos.clone().setY(1.2) };
        break;
      case 'gpu':
        if (rack && gpu) {
          const n = nodePosition(rack, gpu);
          return { pos: new THREE.Vector3(n.x + rack.side * 1.0, Math.max(1.9, n.y + 1.0), n.z + RACK.d / 2 + 4.3), target: new THREE.Vector3(n.x + rack.side * 0.8, Math.max(1.3, n.y + 0.5), n.z + RACK.d / 2 + 0.8) };
        }
        break;
      case 'valve':
        if (rack) {
          const v = valvePosition(rack);
          return { pos: v.clone().add(new THREE.Vector3(0, 1.0, 2.0)), target: v.clone() };
        }
        break;
      case 'cooling':
        return { pos: CDU_POS.clone().add(new THREE.Vector3(-8, 3.8, 5)), target: new THREE.Vector3(0, 0.8, CDU_POS.z - 2.5) };
      case 'thermal':
        return { pos: new THREE.Vector3(0, 14, 7), target: new THREE.Vector3(0, 0, 0) };
      case 'control-room':
        return { pos: CONTROL_ROOM_POS.clone().add(new THREE.Vector3(0, 2.2, 6.0)), target: CONTROL_ROOM_POS.clone().add(new THREE.Vector3(0, 2.1, -1.5)) };
    }
    return { pos: new THREE.Vector3(9, 4.4, 14), target: new THREE.Vector3(0, 0.9, 0) };
  };

  // react to view/selection changes
  useEffect(
    () =>
      useTelemetry.subscribe((s, prev) => {
        if (s.view !== prev.view || s.selectedRack !== prev.selectedRack || s.selectedGpu !== prev.selectedGpu) {
          if (internal.current) return;
          seq.current = null; // a user action always takes over from an event tour
          goal.current = shotFor(s.view, s.selectedRack, s.selectedGpu);
        }
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [racks],
  );
  useEffect(() => {
    goal.current = shotFor('overview');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [racks]);

  useFrame((_, dt) => {
    const st = useTelemetry.getState();
    // ---- start an event sequence from a backend prediction
    // tours start only from the overview, so they never pull the user out of a view they chose
    if (!seq.current && st.pendingFocus && st.followEvents && st.view === 'overview') {
      const g = st.byGpu[st.pendingFocus.gpu_id];
      seq.current = { gpu: st.pendingFocus.gpu_id, step: 0, t: 0, v0: g?.simulated.valve_command ?? 0 };
      st.consumeFocus();
      internal.current = true;
      useTelemetry.setState({ selectedGpu: seq.current.gpu, selectedRack: g?.rack ?? null });
      internal.current = false;
    } else if (st.pendingFocus && !seq.current) st.consumeFocus();

    if (seq.current) {
      const q = seq.current;
      q.t += dt;
      const g = st.byGpu[q.gpu];
      const rackId = g?.rack;
      const hist = st.history[q.gpu] ?? [];
      const slope = hist.length > 6 ? (hist[hist.length - 1].twinTemp - hist[hist.length - 6].twinTemp) / 5 : 1;
      // steps: 0 rack, 1 gpu+forecast (until controller acts), 2 valve (until valve reaches command),
      //        3 coolant pipe, 4 gpu (until temperature stops rising), 5 overview
      const steps: [string, () => boolean, number, number][] = [
        ['rack', () => true, 2.5, 2.5],
        ['gpu', () => !!g && g.simulated.valve_command > q.v0 + 0.02, 2.5, 8],
        ['valve', () => !!g && Math.abs(g.simulated.valve_position - g.simulated.valve_command) < 0.03, 2.5, 10],
        ['cooling', () => true, 3, 3],
        ['gpu', () => slope <= 0.02, 3, 14],
        ['overview', () => true, 2, 2],
      ];
      const [view, done, minT, maxT] = steps[q.step];
      if (q.t < dt * 1.5) {
        internal.current = true;
        if (view === 'gpu' || view === 'rack') useTelemetry.setState({ view: view as 'gpu' | 'rack' });
        internal.current = false;
        goal.current = shotFor(view, rackId, q.gpu);
      }
      if ((q.t >= minT && done()) || q.t >= maxT) {
        q.step += 1;
        q.t = 0;
        if (q.step >= steps.length) {
          seq.current = null;
          internal.current = true;
          useTelemetry.setState({ view: 'overview' });
          internal.current = false;
          goal.current = shotFor('overview');
        }
      }
    }

    // ---- smooth camera move toward the goal; afterwards the user can orbit freely
    if (goal.current && controls.current) {
      camera.position.lerp(goal.current.pos, 1 - Math.exp(-2.2 * dt));
      controls.current.target.lerp(goal.current.target, 1 - Math.exp(-2.2 * dt));
      controls.current.update();
      if (camera.position.distanceTo(goal.current.pos) < 0.05) goal.current = null;
    }
  });

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      maxPolarAngle={Math.PI / 2.05}
      minDistance={1}
      maxDistance={40}
      onStart={() => {
        if (!seq.current) goal.current = null; // user takes over
      }}
    />
  );
}
