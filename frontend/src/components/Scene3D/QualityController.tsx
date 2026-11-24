/**
 * QualityController: Monitors real-time frame budget, samples renderer metrics
 * (draw calls, triangles, FPS), manages automatic quality tier transitions,
 * and handles WebGL context loss/restoration.
 */

import React, { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { setStore, useStore } from "../../store/useStore";

export const QualityController: React.FC = () => {
  const { gl } = useThree();
  const { qualityTier } = useStore();

  const frameCount = useRef(0);
  const lastTime = useRef(performance.now());
  const slowFramesCount = useRef(0);
  const fastFramesCount = useRef(0);

  // Monitor WebGL Context Loss / Restoration
  useEffect(() => {
    const canvas = gl.domElement;
    if (!canvas) return;

    const handleContextLost = (e: Event) => {
      e.preventDefault();
      console.warn("[Scene3D] WebGL context lost. Gracefully falling back to 2D view.");
      setStore({ viewMode: "2d" });
    };

    const handleContextRestored = () => {
      console.info("[Scene3D] WebGL context restored.");
    };

    canvas.addEventListener("webglcontextlost", handleContextLost);
    canvas.addEventListener("webglcontextrestored", handleContextRestored);

    return () => {
      canvas.removeEventListener("webglcontextlost", handleContextLost);
      canvas.removeEventListener("webglcontextrestored", handleContextRestored);
    };
  }, [gl]);

  // Frame timing and diagnostics sampler
  useFrame(() => {
    frameCount.current++;
    const now = performance.now();
    const elapsed = now - lastTime.current;

    if (elapsed >= 1000) {
      const currentFps = Math.round((frameCount.current * 1000) / elapsed);
      const drawCalls = gl.info.render.calls;
      const triangles = gl.info.render.triangles;

      // Auto quality scaling with hysteresis
      if (currentFps < 35) {
        slowFramesCount.current++;
        fastFramesCount.current = 0;
        if (slowFramesCount.current >= 3) {
          if (qualityTier === "ultra") setStore({ qualityTier: "high" });
          else if (qualityTier === "high") setStore({ qualityTier: "medium" });
          else if (qualityTier === "medium") setStore({ qualityTier: "low" });
          slowFramesCount.current = 0;
        }
      } else if (currentFps >= 58) {
        fastFramesCount.current++;
        slowFramesCount.current = 0;
        if (fastFramesCount.current >= 5) {
          if (qualityTier === "low") setStore({ qualityTier: "medium" });
          else if (qualityTier === "medium") setStore({ qualityTier: "high" });
          fastFramesCount.current = 0;
        }
      }

      setStore({
        diagnostics: {
          fps: currentFps,
          drawCalls,
          triangles,
          tier: qualityTier,
        },
      });

      frameCount.current = 0;
      lastTime.current = now;
    }
  });

  return null;
};
