"use client";

import React, { useRef, useEffect, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

interface StarNode {
  name: string;
  toi_id?: number;
  ra: number;
  dec: number;
  distance: number;
  ruwe: number;
  severity: 'normal' | 'warning' | 'critical';
  healthScore: number;
}

interface VisualizerProps {
  targetStar: StarNode;
  comparisonStar?: StarNode;
  otherStars?: StarNode[];
  colorEncoding?: 'distance' | 'severity' | 'health';
  coordinateMode?: 'sun' | 'galactic_center';
  onSelectStar?: (starName: string) => void;
}

export default function GalacticVisualizer({
  targetStar,
  comparisonStar,
  otherStars = [],
  colorEncoding = 'severity',
  coordinateMode = 'sun',
  onSelectStar
}: VisualizerProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [hoveredStar, setHoveredStar] = useState<string | null>(null);
  const [selectedStarDetails, setSelectedStarDetails] = useState<string | null>(null);

  // Conversion formula: RA/Dec/Dist to Cartesian
  const getCoordinates = (ra: number, dec: number, dist: number) => {
    const raRad = (ra * Math.PI) / 180;
    const decRad = (dec * Math.PI) / 180;

    // Relative to Sun
    let x = dist * Math.cos(decRad) * Math.cos(raRad);
    let y = dist * Math.cos(decRad) * Math.sin(raRad);
    let z = dist * Math.sin(decRad);

    if (coordinateMode === 'galactic_center') {
      // Shift relative to Galactic Center (Sun is at X = -8000 pc)
      x -= 8000;
    }
    return new THREE.Vector3(x, y, z);
  };

  const getStarColor = (star: StarNode) => {
    if (colorEncoding === 'distance') {
      if (star.distance < 100) return 0x10b981; // green
      if (star.distance < 500) return 0x0ea5e9; // blue
      return 0xa855f7; // purple
    }
    if (colorEncoding === 'health') {
      if (star.healthScore > 0.85) return 0x10b981; // green
      if (star.healthScore > 0.5) return 0xf59e0b; // amber
      return 0xef4444; // red
    }
    // Severity
    if (star.severity === 'critical') return 0xef4444; // red
    if (star.severity === 'warning') return 0xf59e0b; // amber
    return 0x10b981; // green
  };

  useEffect(() => {
    if (!mountRef.current) return;

    const width = mountRef.current.clientWidth || 400;
    const height = mountRef.current.clientHeight || 300;

    // 1. Setup Scene, Camera, Renderer
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x020617);

    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 50000);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mountRef.current.appendChild(renderer.domElement);

    // 2. Setup Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // 3. Grid / Plane Overlays
    const planeSize = 3000;
    const gridHelper = new THREE.GridHelper(planeSize, 30, 0x1e293b, 0x0f172a);
    gridHelper.position.y = coordinateMode === 'galactic_center' ? 0 : -50;
    scene.add(gridHelper);

    // Galactic Plane marker ring (if GC mode)
    if (coordinateMode === 'galactic_center') {
      const ringGeo = new THREE.RingGeometry(7500, 8500, 64);
      const ringMat = new THREE.MeshBasicMaterial({ color: 0x1e1b4b, side: THREE.DoubleSide, transparent: true, opacity: 0.1 });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = Math.PI / 2;
      scene.add(ring);
    }

    // Solar neighborhood sphere
    const solarSphereGeo = new THREE.SphereGeometry(250, 16, 16);
    const solarSphereMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, wireframe: true, transparent: true, opacity: 0.03 });
    const solarSphere = new THREE.Mesh(solarSphereGeo, solarSphereMat);
    solarSphere.position.set(coordinateMode === 'galactic_center' ? -8000 : 0, 0, 0);
    scene.add(solarSphere);

    // 4. Create Sun
    const sunPos = new THREE.Vector3(coordinateMode === 'galactic_center' ? -8000 : 0, 0, 0);
    const sunGeo = new THREE.SphereGeometry(6, 16, 16);
    const sunMat = new THREE.MeshBasicMaterial({ color: 0xeab308 });
    const sun = new THREE.Mesh(sunGeo, sunMat);
    sun.position.copy(sunPos);
    scene.add(sun);

    // 5. Plot Stars
    const starObjects: THREE.Object3D[] = [];
    const starDataMap = new Map<string, StarNode>();

    const plotStar = (star: StarNode, isTarget = false, isCompare = false) => {
      const pos = getCoordinates(star.ra, star.dec, star.distance);
      const size = isTarget ? 8 : isCompare ? 8 : 4;
      const geo = new THREE.SphereGeometry(size, 16, 16);
      const color = getStarColor(star);
      const mat = new THREE.MeshBasicMaterial({ color });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.copy(pos);
      mesh.name = star.name;
      scene.add(mesh);
      starObjects.push(mesh);
      starDataMap.set(star.name, star);

      // Add selection ring if target or compare
      if (isTarget || isCompare) {
        const ringGeo = new THREE.RingGeometry(size * 1.5, size * 2.0, 16);
        const ringMat = new THREE.MeshBasicMaterial({ color: isTarget ? 0x38bdf8 : 0xf43f5e, side: THREE.DoubleSide });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.position.copy(pos);
        ring.lookAt(camera.position);
        scene.add(ring);
      }

      // Connecting line to Sun
      const lineMat = new THREE.LineBasicMaterial({ color: 0x334155, transparent: true, opacity: 0.4 });
      const points = [sunPos, pos];
      const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
      const line = new THREE.Line(lineGeo, lineMat);
      scene.add(line);
    };

    // Plot main target
    plotStar(targetStar, true);

    // Plot comparison target
    if (comparisonStar) {
      plotStar(comparisonStar, false, true);
    }

    // Plot exoplanet hosts
    otherStars.forEach(s => {
      if (s.name !== targetStar.name && (!comparisonStar || s.name !== comparisonStar.name)) {
        plotStar(s);
      }
    });

    // Set initial camera position relative to target
    const targetPos = getCoordinates(targetStar.ra, targetStar.dec, targetStar.distance);
    camera.position.set(targetPos.x, targetPos.y + 300, targetPos.z + 800);
    controls.target.copy(targetPos);
    controls.update();

    // 6. Interactive Raycasting / Clicks
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const handleMouseClick = (event: MouseEvent) => {
      if (!mountRef.current) return;
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(starObjects);

      if (intersects.length > 0) {
        const obj = intersects[0].object;
        const star = starDataMap.get(obj.name);
        if (star) {
          setSelectedStarDetails(`${star.name} // Dist: ${star.distance.toFixed(1)} pc // RUWE: ${star.ruwe.toFixed(2)}`);
          if (onSelectStar) onSelectStar(star.name);
        }
      } else {
        setSelectedStarDetails(null);
      }
    };

    const handleMouseMove = (event: MouseEvent) => {
      if (!mountRef.current) return;
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(starObjects);

      if (intersects.length > 0) {
        setHoveredStar(intersects[0].object.name);
      } else {
        setHoveredStar(null);
      }
    };

    renderer.domElement.addEventListener('click', handleMouseClick);
    renderer.domElement.addEventListener('mousemove', handleMouseMove);

    // 7. Animation Loop
    let animationFrameId: number;
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Resize Handler
    const handleResize = () => {
      if (!mountRef.current) return;
      const w = mountRef.current.clientWidth;
      const h = mountRef.current.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      if (renderer && renderer.domElement) {
        renderer.domElement.removeEventListener('click', handleMouseClick);
        renderer.domElement.removeEventListener('mousemove', handleMouseMove);
        mountRef.current?.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [targetStar, comparisonStar, otherStars, colorEncoding, coordinateMode]);

  return (
    <div className="w-full h-full relative flex flex-col justify-between">
      {/* 3D Container viewport */}
      <div ref={mountRef} className="w-full flex-1 rounded-lg border border-slate-900 overflow-hidden relative">
        {hoveredStar && (
          <div className="absolute top-3 left-3 bg-slate-950/80 border border-slate-800 px-3 py-1.5 rounded text-[10px] font-mono text-slate-300 pointer-events-none uppercase">
            Hover: <span className="text-white font-bold">{hoveredStar}</span>
          </div>
        )}
        
        {selectedStarDetails && (
          <div className="absolute bottom-3 left-3 right-3 bg-slate-950/90 border border-sky-500/30 px-3 py-2 rounded-lg text-[10px] font-mono text-sky-400 flex justify-between items-center pointer-events-auto">
            <span>{selectedStarDetails}</span>
            <button 
              onClick={() => setSelectedStarDetails(null)} 
              className="text-slate-500 hover:text-white"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Coordinate mode info panel */}
      <div className="flex justify-between items-center text-[9px] font-mono text-slate-500 mt-2 px-1">
        <span>Galactic plane size: 3000 pc</span>
        <span>Sun: (0,0,0) // Target: ({targetStar.distance.toFixed(0)} pc)</span>
      </div>
    </div>
  );
}
