import React, { useEffect, useRef } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import { CameraControls } from '@react-three/drei';
import { useTelemetryStore } from '../../store/telemetryStore';
import * as THREE from 'three';

export function CameraController() {
  const { currentView } = useTelemetryStore();
  const controlsRef = useRef<CameraControls>(null);

  useEffect(() => {
    if (!controlsRef.current) return;
    const controls = controlsRef.current;

    switch (currentView) {
      case 'overview':
        controls.setLookAt(0, 12, 18, 0, 0, 0, true);
        break;
      case 'rack':
        controls.setLookAt(0, 5, 5, 0, 1, 0, true);
        break;
      case 'gpu':
        controls.setLookAt(0, 1, 2, 0, 1, 0, true);
        break;
      case 'cooling':
        controls.setLookAt(-8, 8, 15, -8, 1, -5, true);
        break;
      case 'thermal':
        controls.setLookAt(0, 15, 12, 0, 0, 0, true);
        break;
      case 'control-room':
        controls.setLookAt(15, 5, 0, 15, 5, -10, true);
        break;
    }
  }, [currentView]);

  return <CameraControls ref={controlsRef} />;
}
