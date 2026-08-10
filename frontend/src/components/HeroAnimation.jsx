import React, { useEffect, useRef } from 'react';

export default function HeroAnimation() {
  const containerRef = useRef(null);

  useEffect(() => {
    let animId;
    let renderer, scene, camera, anchor, core, geometry, material, coreGeo, coreMat;
    let handleResize;

    const initThree = () => {
      const THREE = window.THREE;
      if (!THREE || !containerRef.current) return;

      const container = containerRef.current;
      const width = container.clientWidth || window.innerWidth;
      const height = container.clientHeight || window.innerHeight;

      scene = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });

      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

      // Clear previous canvas if any
      while (container.firstChild) {
        container.removeChild(container.firstChild);
      }
      container.appendChild(renderer.domElement);

      // Outer Grid (Silver / Frost Gray Wireframe)
      geometry = new THREE.IcosahedronGeometry(2.5, 1);
      material = new THREE.MeshPhongMaterial({
        color: 0xa1a4a5,
        wireframe: true,
        transparent: true,
        opacity: 0.5,
        emissive: 0x464a4d,
        emissiveIntensity: 0.3
      });
      anchor = new THREE.Mesh(geometry, material);
      scene.add(anchor);

      // Luminous Core (Glowing Orange)
      coreGeo = new THREE.IcosahedronGeometry(1.2, 0);
      coreMat = new THREE.MeshPhongMaterial({
        color: 0xff801f,
        emissive: 0xff5900,
        emissiveIntensity: 0.8,
        transparent: true,
        opacity: 0.6
      });
      core = new THREE.Mesh(coreGeo, coreMat);
      scene.add(core);

      const light = new THREE.PointLight(0xffffff, 2, 100);
      light.position.set(5, 5, 5);
      scene.add(light);

      const ambientLight = new THREE.AmbientLight(0x404040);
      scene.add(ambientLight);

      camera.position.z = 6;

      const animate = () => {
        animId = requestAnimationFrame(animate);

        if (anchor) {
          anchor.rotation.x += 0.0015;
          anchor.rotation.y += 0.002;
        }

        if (core) {
          core.rotation.x -= 0.004;
          core.rotation.y -= 0.004;

          const scale = 1 + Math.sin(Date.now() * 0.001) * 0.05;
          core.scale.set(scale, scale, scale);
        }

        renderer.render(scene, camera);
      };

      handleResize = () => {
        if (!containerRef.current) return;
        const newWidth = containerRef.current.clientWidth || window.innerWidth;
        const newHeight = containerRef.current.clientHeight || window.innerHeight;
        camera.aspect = newWidth / newHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(newWidth, newHeight);
      };

      window.addEventListener('resize', handleResize);
      animate();
    };

    if (window.THREE) {
      initThree();
    } else {
      const existingScript = document.getElementById('three-js-script');
      if (!existingScript) {
        const script = document.createElement('script');
        script.id = 'three-js-script';
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r125/three.min.js';
        script.async = true;
        script.onload = () => initThree();
        document.head.appendChild(script);
      } else {
        existingScript.addEventListener('load', initThree);
      }
    }

    return () => {
      if (animId) cancelAnimationFrame(animId);
      if (handleResize) window.removeEventListener('resize', handleResize);
      if (renderer && renderer.domElement && containerRef.current && containerRef.current.contains(renderer.domElement)) {
        containerRef.current.removeChild(renderer.domElement);
      }
      if (renderer) renderer.dispose();
      if (geometry) geometry.dispose();
      if (material) material.dispose();
      if (coreGeo) coreGeo.dispose();
      if (coreMat) coreMat.dispose();
    };
  }, []);

  return (
    <div 
      ref={containerRef} 
      className="absolute inset-0 w-full h-full bg-transparent -z-10 pointer-events-none opacity-60"
    />
  );
}
