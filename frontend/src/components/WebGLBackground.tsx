import React, { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import * as THREE from 'three';

export const WebGLBackground: React.FC = () => {
  const location = useLocation();
  const mountRef = useRef<HTMLDivElement | null>(null);

  // Exclude 3D animation strictly in the interview room (/conversation)
  const isInterviewRoom = location.pathname.startsWith('/conversation');

  useEffect(() => {
    if (isInterviewRoom) return;

    const container = mountRef.current;
    if (!container) return;

    // 1. Scene, Camera, and Renderer setup
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020617, 0.0018);

    const camera = new THREE.PerspectiveCamera(
      60,
      window.innerWidth / window.innerHeight,
      1,
      1000
    );
    camera.position.z = 450;

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x020617, 1);
    container.appendChild(renderer.domElement);

    // 2. Interactive 3D Particle Constellation
    const particleCount = 750;
    const positions = new Float32Array(particleCount * 3);
    const velocities = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    const colorPalette = [
      new THREE.Color('#6366F1'), // Indigo
      new THREE.Color('#8B5CF6'), // Purple
      new THREE.Color('#14B8A6'), // Teal
      new THREE.Color('#38BDF8'), // Sky Blue
    ];

    const radius = 600;
    for (let i = 0; i < particleCount; i++) {
      const i3 = i * 3;
      positions[i3] = (Math.random() - 0.5) * radius * 2;
      positions[i3 + 1] = (Math.random() - 0.5) * radius * 1.5;
      positions[i3 + 2] = (Math.random() - 0.5) * radius * 1.8;

      velocities[i3] = (Math.random() - 0.5) * 0.35;
      velocities[i3 + 1] = (Math.random() - 0.5) * 0.35;
      velocities[i3 + 2] = (Math.random() - 0.5) * 0.35;

      const col = colorPalette[Math.floor(Math.random() * colorPalette.length)];
      colors[i3] = col.r;
      colors[i3 + 1] = col.g;
      colors[i3 + 2] = col.b;
    }

    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    // Create soft circular sprite for points
    const canvas = document.createElement('canvas');
    canvas.width = 32;
    canvas.height = 32;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      const grad = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
      grad.addColorStop(0, 'rgba(255,255,255,1)');
      grad.addColorStop(0.3, 'rgba(255,255,255,0.8)');
      grad.addColorStop(0.7, 'rgba(255,255,255,0.2)');
      grad.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 32, 32);
    }
    const particleTexture = new THREE.CanvasTexture(canvas);

    const particleMaterial = new THREE.PointsMaterial({
      size: 4.5,
      map: particleTexture,
      transparent: true,
      vertexColors: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const particleSystem = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particleSystem);

    // 3. Dynamic Constellation Connector Lines
    const maxLineConnections = 250;
    const linePositions = new Float32Array(maxLineConnections * 2 * 3);
    const lineColors = new Float32Array(maxLineConnections * 2 * 3);

    const lineGeometry = new THREE.BufferGeometry();
    lineGeometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
    lineGeometry.setAttribute('color', new THREE.BufferAttribute(lineColors, 3));

    const lineMaterial = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const linesMesh = new THREE.LineSegments(lineGeometry, lineMaterial);
    scene.add(linesMesh);

    // 4. Floating 3D Geometric Polygonal Core (Icosahedron & Inner Core)
    const icosaGroup = new THREE.Group();
    icosaGroup.position.set(180, 40, -120);

    const outerGeom = new THREE.IcosahedronGeometry(110, 1);
    const outerMat = new THREE.MeshBasicMaterial({
      color: 0x6366F1,
      wireframe: true,
      transparent: true,
      opacity: 0.18,
    });
    const outerMesh = new THREE.Mesh(outerGeom, outerMat);
    icosaGroup.add(outerMesh);

    const innerGeom = new THREE.IcosahedronGeometry(75, 0);
    const innerMat = new THREE.MeshBasicMaterial({
      color: 0x14B8A6,
      wireframe: true,
      transparent: true,
      opacity: 0.28,
    });
    const innerMesh = new THREE.Mesh(innerGeom, innerMat);
    icosaGroup.add(innerMesh);

    // Floating torus ring
    const ringGeom = new THREE.TorusGeometry(140, 0.8, 16, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x8B5CF6,
      transparent: true,
      opacity: 0.22,
    });
    const ringMesh = new THREE.Mesh(ringGeom, ringMat);
    ringMesh.rotation.x = Math.PI / 3;
    icosaGroup.add(ringMesh);

    scene.add(icosaGroup);

    // 5. Mouse Parallax & Dynamic Tracking
    let mouseX = 0;
    let mouseY = 0;
    let targetCameraX = 0;
    let targetCameraY = 0;

    const handleMouseMove = (event: MouseEvent) => {
      mouseX = (event.clientX / window.innerWidth) * 2 - 1;
      mouseY = -(event.clientY / window.innerHeight) * 2 + 1;
      targetCameraX = mouseX * 80;
      targetCameraY = mouseY * 60;
    };
    window.addEventListener('mousemove', handleMouseMove, { passive: true });

    // 6. Responsive resize listener
    const handleResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener('resize', handleResize);

    // 7. Animation Frame Render Loop
    let animationFrameId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Camera parallax interpolation
      camera.position.x += (targetCameraX - camera.position.x) * 0.035;
      camera.position.y += (targetCameraY - camera.position.y) * 0.035;
      camera.lookAt(0, 0, 0);

      // Rotate geometric core
      icosaGroup.rotation.y = elapsed * 0.12;
      icosaGroup.rotation.x = Math.sin(elapsed * 0.08) * 0.2;
      icosaGroup.position.y = 40 + Math.sin(elapsed * 0.6) * 15;
      innerMesh.rotation.y = -elapsed * 0.18;
      ringMesh.rotation.z = elapsed * 0.09;

      // Update particle positions
      const posAttr = particleGeometry.getAttribute('position') as THREE.BufferAttribute;
      const posArray = posAttr.array as Float32Array;

      for (let i = 0; i < particleCount; i++) {
        const i3 = i * 3;
        posArray[i3] += velocities[i3];
        posArray[i3 + 1] += velocities[i3 + 1];
        posArray[i3 + 2] += velocities[i3 + 2];

        // Wrap boundaries
        if (Math.abs(posArray[i3]) > radius) velocities[i3] *= -1;
        if (Math.abs(posArray[i3 + 1]) > radius * 0.8) velocities[i3 + 1] *= -1;
        if (Math.abs(posArray[i3 + 2]) > radius * 0.9) velocities[i3 + 2] *= -1;
      }
      posAttr.needsUpdate = true;

      // Connect nearby particles with glowing lines
      let connectionCount = 0;
      const linePosAttr = lineGeometry.getAttribute('position') as THREE.BufferAttribute;
      const lineColAttr = lineGeometry.getAttribute('color') as THREE.BufferAttribute;
      const linePosArr = linePosAttr.array as Float32Array;
      const lineColArr = lineColAttr.array as Float32Array;

      const connectionThreshold = 65;
      // Sample a subset for high 60fps performance
      for (let i = 0; i < 180 && connectionCount < maxLineConnections; i++) {
        const i3 = i * 3;
        for (let j = i + 1; j < 180 && connectionCount < maxLineConnections; j++) {
          const j3 = j * 3;
          const dx = posArray[i3] - posArray[j3];
          const dy = posArray[i3 + 1] - posArray[j3 + 1];
          const dz = posArray[i3 + 2] - posArray[j3 + 2];
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

          if (dist < connectionThreshold) {
            const lineIdx = connectionCount * 6;
            linePosArr[lineIdx] = posArray[i3];
            linePosArr[lineIdx + 1] = posArray[i3 + 1];
            linePosArr[lineIdx + 2] = posArray[i3 + 2];

            linePosArr[lineIdx + 3] = posArray[j3];
            linePosArr[lineIdx + 4] = posArray[j3 + 1];
            linePosArr[lineIdx + 5] = posArray[j3 + 2];

            const alpha = 1.0 - dist / connectionThreshold;
            lineColArr[lineIdx] = 0.39 * alpha;
            lineColArr[lineIdx + 1] = 0.40 * alpha;
            lineColArr[lineIdx + 2] = 0.95 * alpha;

            lineColArr[lineIdx + 3] = 0.08 * alpha;
            lineColArr[lineIdx + 4] = 0.72 * alpha;
            lineColArr[lineIdx + 5] = 0.65 * alpha;

            connectionCount++;
          }
        }
      }
      lineGeometry.setDrawRange(0, connectionCount * 2);
      linePosAttr.needsUpdate = true;
      lineColAttr.needsUpdate = true;

      // Particle system subtle rotation
      particleSystem.rotation.y = elapsed * 0.02;

      renderer.render(scene, camera);
    };

    animate();

    // 8. Cleanup on unmount or route change
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);

      particleGeometry.dispose();
      particleMaterial.dispose();
      particleTexture.dispose();
      lineGeometry.dispose();
      lineMaterial.dispose();
      outerGeom.dispose();
      outerMat.dispose();
      innerGeom.dispose();
      innerMat.dispose();
      ringGeom.dispose();
      ringMat.dispose();
      renderer.dispose();

      if (container && renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [isInterviewRoom]);

  // If in the interview room (/conversation), render nothing
  if (isInterviewRoom) {
    return null;
  }

  return (
    <div className="fixed inset-0 pointer-events-none -z-10 overflow-hidden">
      {/* Three.js Canvas Container */}
      <div ref={mountRef} className="absolute inset-0 w-full h-full" />

      {/* Ambient Gradient Glows */}
      <div className="absolute top-[-15%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-indigo-600/10 blur-[140px] pointer-events-none" />
      <div className="absolute bottom-[-15%] right-[-10%] w-[50vw] h-[50vw] rounded-full bg-teal-500/10 blur-[140px] pointer-events-none" />
      <div className="absolute top-[40%] right-[15%] w-[35vw] h-[35vw] rounded-full bg-purple-600/8 blur-[120px] pointer-events-none" />

      {/* Cinematic Vignette Overlay to ensure 100% foreground readability */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/40 via-transparent to-slate-950/80 pointer-events-none" />
    </div>
  );
};
