import React from 'react';
import { Text } from '@react-three/drei';
import { useSpring, animated } from '@react-spring/three';

interface Props {
  position: [number, number, number];
  valvePosition: number;
}

export function Valve({ position, valvePosition }: Props) {
  const { rotation } = useSpring({
    rotation: [0, 0, (valvePosition / 100) * (Math.PI / 2)] as [number, number, number]
  });

  return (
    <group position={position}>
      <mesh>
        <cylinderGeometry args={[0.1, 0.1, 0.3, 16]} />
        <meshStandardMaterial color="#555" />
      </mesh>
      <animated.group rotation={rotation}>
        <mesh position={[0, 0.15, 0]} rotation={[Math.PI/2, 0, 0]}>
          <torusGeometry args={[0.08, 0.02, 16, 32]} />
          <meshStandardMaterial color={valvePosition > 50 ? "#00ff00" : "#00e5ff"} />
        </mesh>
      </animated.group>
      <Text position={[0, 0.3, 0]} fontSize={0.05} color="#fff">
        {`${Math.round(valvePosition)}%`}
      </Text>
    </group>
  );
}
