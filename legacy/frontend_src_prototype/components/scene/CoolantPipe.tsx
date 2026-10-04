import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export function CoolantPipe() {
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  useFrame((state) => {
    if (materialRef.current) {
      materialRef.current.uniforms.time.value = state.clock.elapsedTime;
    }
  });

  return (
    <mesh>
      <tubeGeometry args={[new THREE.CatmullRomCurve3([
        new THREE.Vector3(-8, 0.5, -5),
        new THREE.Vector3(-8, 2.5, -5),
        new THREE.Vector3(0, 2.5, -5),
        new THREE.Vector3(0, 2.5, 0),
      ]), 64, 0.05, 8, false]} />
      <shaderMaterial
        ref={materialRef}
        uniforms={{
          time: { value: 0 },
          uSpeed: { value: 1.0 },
          color: { value: new THREE.Color(0x00e5ff) }
        }}
        vertexShader={`
          varying vec2 vUv;
          void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `}
        fragmentShader={`
          uniform float time;
          uniform float uSpeed;
          uniform vec3 color;
          varying vec2 vUv;
          void main() {
            float pulse = sin(vUv.x * 20.0 - time * 5.0 * uSpeed) * 0.5 + 0.5;
            gl_FragColor = vec4(color * (0.5 + pulse * 0.5), 0.8);
          }
        `}
        transparent
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}
