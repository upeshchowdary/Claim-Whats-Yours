import { useEffect, useMemo, useRef, useState } from "react";
import type { JSX } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import type { Group } from "three";

// Single allowed hex literal: fallback when the --primary CSS variable is unavailable.
const FALLBACK_PRIMARY = "#4A2BC2";

const NODE_POSITIONS: [number, number, number][] = [
  [0, 1.6, 0.4],
  [1.4, 0.7, -0.3],
  [1.6, -0.8, 0.2],
  [0.5, -1.6, -0.4],
  [-0.7, -1.5, 0.3],
  [-1.5, -0.5, -0.2],
  [-1.4, 0.9, 0.5],
  [-0.2, 0.2, 1.1],
  [0.3, 0.4, -1.2],
];

const LINKS: [number, number][] = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [4, 5],
  [5, 6],
  [6, 0],
  [7, 0],
  [7, 3],
  [7, 5],
  [8, 1],
  [8, 4],
];

function readPrimaryColor(): string {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue("--primary")
    .trim();
  return value || FALLBACK_PRIMARY;
}

function HeroGroup({ color }: { color: string }): JSX.Element {
  const groupRef = useRef<Group>(null);
  const pointer = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      pointer.current = {
        x: (event.clientX / window.innerWidth) * 2 - 1,
        y: (event.clientY / window.innerHeight) * 2 - 1,
      };
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  useFrame((_state, delta) => {
    const group = groupRef.current;
    if (!group) return;
    group.rotation.y += delta * 0.1;
    const targetX = pointer.current.y * 0.15;
    const targetY = pointer.current.x * 0.15;
    group.rotation.x += (targetX - group.rotation.x) * 0.05;
    group.position.x += (pointer.current.x * 0.2 - group.position.x) * 0.05;
    group.position.y += (-pointer.current.y * 0.2 - group.position.y) * 0.05;
  });

  const linePoints = useMemo(
    () =>
      LINKS.map(([from, to]) => [
        NODE_POSITIONS[from],
        NODE_POSITIONS[to],
      ]),
    [],
  );

  return (
    <group ref={groupRef}>
      <ambientLight intensity={0.8} />
      <directionalLight position={[3, 4, 5]} intensity={1.2} />

      {NODE_POSITIONS.map((position, index) => (
        <mesh key={`node-${index}`} position={position}>
          <sphereGeometry args={[0.16, 24, 24]} />
          <meshStandardMaterial color={color} />
        </mesh>
      ))}

      {linePoints.map((points, index) => (
        <Line
          key={`link-${index}`}
          points={points}
          color={color}
          lineWidth={1}
          transparent
          opacity={0.5}
        />
      ))}

      <mesh position={[0, 0, -0.5]} rotation={[0.4, 0.3, 0]}>
        <icosahedronGeometry args={[1.9, 0]} />
        <meshStandardMaterial
          color={color}
          transparent
          opacity={0.15}
          depthWrite={false}
        />
      </mesh>
      <mesh position={[0, 0, -0.9]} rotation={[0.2, 0.6, 0.1]}>
        <dodecahedronGeometry args={[2.4, 0]} />
        <meshStandardMaterial
          color={color}
          transparent
          opacity={0.15}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

export default function HeroScene3D(): JSX.Element {
  const [color, setColor] = useState<string>(FALLBACK_PRIMARY);

  useEffect(() => {
    setColor(readPrimaryColor());
  }, []);

  return (
    <div className="pointer-events-none h-full w-full" aria-hidden="true">
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 6], fov: 45 }}
        gl={{ antialias: true, alpha: true }}
      >
        <HeroGroup color={color} />
      </Canvas>
    </div>
  );
}
