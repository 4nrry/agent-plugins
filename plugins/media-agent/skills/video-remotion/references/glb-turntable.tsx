// Referencia verificada: turntable de um .glb dentro do Remotion com @remotion/three.
// Testado com remotion/@remotion/three 4.0.526, three 0.186.0, @react-three/fiber 9.8.0,
// renderizado com --gl=angle (ou vulkan). Com --gl=swangle o canvas sai vazio, sem erro.
//
//   <Composition id="Giro" component={GlbTurntable} width={900} height={900} fps={30} durationInFrames={120}
//                defaultProps={{ src: "device.glb" }} />
//   <Composition id="Dolly" component={GlbTurntable} width={1080} height={1920} fps={30} durationInFrames={150}
//                defaultProps={{ src: "device.glb", hero: true }} />
//
// Giro com fundo transparente: --codec prores --prores-profile 4444 --pixel-format yuva444p10le --image-format png
import React, { useEffect, useMemo, useRef, useState } from "react";
import { AbsoluteFill, continueRender, delayRender, interpolate, Easing, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { useThree } from "@react-three/fiber";

/** Carrega o GLB uma vez e segura o render ate ele existir (sem isso o 1o frame sai vazio). */
function useGlb(url: string) {
  const [scene, setScene] = useState<THREE.Group | null>(null);
  const [handle] = useState(() => delayRender("glb"));
  useEffect(() => {
    // continueRender so depois de um frame desenhado com o modelo na cena.
    new GLTFLoader().load(url, (g) => setScene(g.scene), undefined, (e) => { console.error('GLB', e); continueRender(handle); });
  }, [url, handle]);
  return { scene, release: () => continueRender(handle) };
}

/** Iluminacao por ambiente (IBL)  e o que substitui as area lights do Cycles. */
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
  // O ThreeCanvas so desenha quando o frame do Remotion muda; forcar um desenho com o modelo antes de liberar o render.
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
  // Mesma camera do turntable.py da skill turntable-blender: lente 65 mm (~31 graus de FOV), a 2,3x o tamanho, em 3/4.
  const d = size * 2.3;
  const cam = camera as THREE.PerspectiveCamera;
  if (!hero) {
    cam.fov = 31;
    cam.position.set(d * 0.8, d * 0.45, d * 0.9);
    cam.lookAt(0, 0, 0);
  } else {
    // O que o PNG pre-renderizado nao faz: a camera se move. Dolly-in em 3/4 descendo ate a altura dos detalhes.
    const t = interpolate(frame, [0, durationInFrames - 1], [0, 1], { easing: Easing.bezier(0.45, 0, 0.2, 1) });
    cam.fov = interpolate(t, [0, 1], [36, 30]);
    const r = size * interpolate(t, [0, 1], [3.6, 2.5]);
    const a = interpolate(t, [0, 1], [0.95, 0.55]);
    cam.position.set(Math.sin(a) * r, size * interpolate(t, [0, 1], [1.1, 0.25]), Math.cos(a) * r);
    cam.lookAt(0, size * interpolate(t, [0, 1], [0.05, -0.08]), 0);
  }
  // near/far relativos ao tamanho: o GLB pode vir em mm, e far fixo em 100 corta o modelo inteiro.
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
      {/* key, fill e rim fixos, nas posicoes do turntable.py (Blender z-up  three y-up): o modelo gira, a luz nao */}
      <directionalLight position={[d * 0.6, d * 0.9, d * 0.6]} intensity={2.4} color="#fff5e6" />
      <directionalLight position={[-d * 0.9, d * 0.3, d * 0.4]} intensity={0.8} color="#ebf2ff" />
      <directionalLight position={[-d * 0.3, d * 0.7, -d * 0.9]} intensity={2.0} />
    </>
  );
};

export const GlbTurntable: React.FC<{ src?: string; hero?: boolean; background?: string }> = ({ src = "model.glb", hero = false, background = "#F5F0E8" }) => {
  const { width, height } = useVideoConfig();
  // O GLB carrega fora do Canvas: dentro dele o reconciler do R3F nao segura o delayRender.
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
