"use client";

import React, { useEffect, useRef, useState } from "react";
import { createAudioAnalyser, type LocalAudioTrack, type RemoteAudioTrack } from "livekit-client";

interface AudioVisualizerProps {
  audioTrack: LocalAudioTrack | RemoteAudioTrack | null;
  barCount?: number;
  className?: string;
}

export default function AudioVisualizer({ audioTrack, barCount = 7, className = "" }: AudioVisualizerProps) {
  const [audioLevels, setAudioLevels] = useState<number[]>(new Array(barCount).fill(0));
  const animationFrameRef = useRef<number | null>(null);
  const cleanupRef = useRef<(() => Promise<void>) | null>(null);

  useEffect(() => {
    if (!audioTrack || !(audioTrack as any).mediaStream) {
      // Reset levels when no track or track not ready
      setAudioLevels(new Array(barCount).fill(0));
      return;
    }

    // Use LiveKit's createAudioAnalyser utility (same as official components)
    // Use larger fftSize for better frequency resolution
    const { analyser, cleanup } = createAudioAnalyser(audioTrack, {
      fftSize: 2048,
      smoothingTimeConstant: 0.8,
    });

    cleanupRef.current = cleanup;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    // Animation loop
    const updateLevels = () => {
      analyser.getByteFrequencyData(dataArray);

      // Focus on frequency range where voice audio has energy
      // Skip very low frequencies (noise) and very high frequencies (not much voice energy)
      const loPass = 10; // Start from bin 10 to skip DC and very low frequencies
      const hiPass = Math.min(dataArray.length, 300); // Focus on frequencies up to ~6kHz (voice range)
      const relevantData = dataArray.slice(loPass, hiPass);
      
      if (relevantData.length === 0) {
        setAudioLevels(new Array(barCount).fill(0));
        animationFrameRef.current = requestAnimationFrame(updateLevels);
        return;
      }

      // Divide into equal bands but apply amplification to higher frequency bands
      // This makes all bars visible even though voice has less energy in higher frequencies
      const samplesPerBar = Math.floor(relevantData.length / barCount);
      const newLevels: number[] = [];

      for (let i = 0; i < barCount; i++) {
        const start = i * samplesPerBar;
        const end = Math.min(start + samplesPerBar, relevantData.length);
        const bandLength = Math.max(1, end - start);
        
        let sum = 0;
        for (let j = start; j < end; j++) {
          sum += relevantData[j];
        }
        
        const avg = sum / bandLength;
        // Normalize to 0-1 range (0-255 -> 0-1)
        let normalized = avg / 255;
        
        // Apply progressive amplification to higher frequency bands
        // This makes bars 4-7 more visible even with less energy
        // Reduced amplification to prevent all bars from maxing out
        const amplification = 1 + (i / barCount) * 0.5; // Amplify up to 1.5x for highest band
        normalized = Math.min(1, normalized * amplification);
        
        newLevels.push(normalized);
      }

      setAudioLevels(newLevels);
      animationFrameRef.current = requestAnimationFrame(updateLevels);
    };

    updateLevels();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      if (cleanupRef.current) {
        cleanupRef.current();
        cleanupRef.current = null;
      }
    };
  }, [audioTrack, barCount]);

  return (
    <div className={`audio-visualizer ${className}`} style={{ display: "flex", gap: "4px", alignItems: "flex-end", height: "60px", justifyContent: "center" }}>
      {audioLevels.map((level, index) => {
        const height = Math.max(4, level * 50); // Min 4px, max 50px
        return (
          <div
            key={index}
            className="audio-bar"
            style={{
              width: "6px",
              height: `${height}px`,
              backgroundColor: "var(--accent)",
              borderRadius: "3px",
              transition: "height 0.1s ease-out",
              minHeight: "4px",
            }}
          />
        );
      })}
    </div>
  );
}

