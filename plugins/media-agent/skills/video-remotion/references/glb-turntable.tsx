// Verified reference: a .glb turntable inside Remotion with @remotion/three.
// Tested with remotion/@remotion/three 4.0.526, three 0.186.0, @react-three/fiber 9.8.0,
// rendered with --gl=angle (or vulkan). With --gl=swangle the canvas is empty, with no error.
//
//   <Composition id="Turntable" component={GlbTurntable} width={900} height={900} fps={30} durationInFrames={120}
//                defaultProps={{ src: "device.glb" }} />
//   <Composition id="Dolly" component={GlbTurntable} width={1080} height={1920} fps={30} durationInFrames={150}
//                defaultProps={{ src: "device.glb", hero: true }} />
//
// Transparent-background turntable: --codec prores --prores-profile 4444 --pixel-format yuva444p10le --image-format png
import React, { useEffect, useMemo, useRef, useState } from "react";
import { AbsoluteFill, continueRender, delayRender, interpolate, Easing, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { useThree } from "@react-three/fiber";

/** Load the GLB once and hold the render until it exists (otherwise frame 1 is empty). */
function useGlb(url: string) {
  const [scene, setScene] = useState<THREE.Group | null>(null);
  const [handle] = useState(() => delayRender("glb"));
  useEffect(() => {
    // continueRender only after a frame has been drawn with the model in the scene.
    new GLTFLoader().load(url, (g) => setScene(g.scene), undefined, (e) => { console.error('GLB', e); continueRender(handle); });
  }, [url, handle]);
  return { scene, release: () => continueRender(handle) };
}

/** Image-based lighting (IBL) stands in for the Cycles area lights. */
const Env: React.FC = () => {
  const { gl, scene } = useThree();
  useEffect(() => {
    const pm = new THREE.PMREMGenerator(gl);
    scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.28;
    gl.toneMapping = THREE.AgXToneMapping;
    gl.toneMappingExposure = 1.05;
    return () => pm.dispose();
  }, [gl, scene]);
  return null;
};

const Device: React.FC<{ hero: boolean; glb: THREE.Group | null; onDrawn: () => void }> = ({ hero, glb, onDrawn }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const { camera, advance } = useThree();
  const drawn = useRef(false);
  // ThreeCanvas only draws when the Remotion frame changes; force a draw with the model before releasing the render.
  useEffect(() => {
    if (!glb || drawn.current) return;
    drawn.current = true;
    advance(performance.now());
    requestAnimationFrame(onDrawn);
  }, [glb, advance, onDrawn]);
  const fit = useMemo(() => {
    if (!glb) return null;
    const box = new THREE.Box3().setFromObject(glb);
    const center = box.getCenter(new THREE.Vector3());
    const size = Math.max(...box.getSize(new THREE.Vector3()).toArray());
    return { center, size };
  }, [glb]);
  if (!glb || !fit) return null;
  const { center, size } = fit;
  // Same camera as turntable.py in the turntable-blender skill: 65 mm lens (~31 degree FOV), at 2.3x the size, 3/4 view.
  const d = size * 2.3;
  const cam = camera as THREE.PerspectiveCamera;
  if (!hero) {
    cam.fov = 31;
    cam.position.set(d * 0.8, d * 0.45, d * 0.9);
    cam.lookAt(0, 0, 0);
  } else {
    // What pre-rendered PNGs cannot do: move the camera. 3/4 dolly-in, descending to detail height.
    const t = interpolate(frame, [0, durationInFrames - 1], [0, 1], { easing: Easing.bezier(0.45, 0, 0.2, 1) });
    cam.fov = interpolate(t, [0, 1], [36, 30]);
    const r = size * interpolate(t, [0, 1], [3.6, 2.5]);
    const a = interpolate(t, [0, 1], [0.95, 0.55]);
    cam.position.set(Math.sin(a) * r, size * interpolate(t, [0, 1], [1.1, 0.25]), Math.cos(a) * r);
    cam.lookAt(0, size * interpolate(t, [0, 1], [0.05, -0.08]), 0);
  }
  // near/far relative to size: the GLB may be in mm, and a fixed far of 100 clips the whole model.
  cam.near = size / 100; cam.far = size * 100;
  cam.updateProjectionMatrix();
  const rot = hero ? interpolate(frame, [0, durationInFrames], [0.35, -0.35]) : (frame / durationInFrames) * Math.PI * 2;
  return (
    <>
      <group rotation={[0, rot, 0]}>
        <group position={[-center.x, -center.y, -center.z]}>
          <primitive object={glb} />
        </group>
      </group>
      {/* fixed key, fill and rim at the turntable.py positions (Blender z-up, three y-up): the model turns, the lights do not */}
      <directionalLight position={[d * 0.6, d * 0.9, d * 0.6]} intensity={2.4} color="#fff5e6" />
      <directionalLight position={[-d * 0.9, d * 0.3, d * 0.4]} intensity={0.8} color="#ebf2ff" />
      <directionalLight position={[-d * 0.3, d * 0.7, -d * 0.9]} intensity={2.0} />
    </>
  );
};

export const GlbTurntable: React.FC<{ src?: string; hero?: boolean; background?: string }> = ({ src = "model.glb", hero = false, background = "#F5F0E8" }) => {
  const { width, height } = useVideoConfig();
  // The GLB loads outside the Canvas: inside it the R3F reconciler does not hold delayRender.
  const { scene: glb, release } = useGlb(staticFile(src));
  return (
    <AbsoluteFill style={{ background: hero ? background : "transparent" }}>
      <ThreeCanvas width={width} height={height} gl={{ alpha: true, antialias: true, preserveDrawingBuffer: true }} camera={{ position: [0, 0, 5], near: 0.01, far: 100 }}>
        <Env />
        <Device hero={hero} glb={glb} onDrawn={release} />
      </ThreeCanvas>
    </AbsoluteFill>
  );
};
