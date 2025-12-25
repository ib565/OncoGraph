"use client";

import React, { useEffect, useRef, useState } from "react";
import type { Track } from "livekit-client";

interface AudioVisualizerProps {
  audioTrack: Track | null;
  barCount?: number;
  className?: string;
}

export default function AudioVisualizer({ audioTrack, barCount = 7, className = "" }: AudioVisualizerProps) {
  const [audioLevels, setAudioLevels] = useState<number[]>(new Array(barCount).fill(0));
  const animationFrameRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const dataArrayRef = useRef<Uint8Array | null>(null);

  useEffect(() => {
    if (!audioTrack) {
      // Reset levels when no track
      setAudioLevels(new Array(barCount).fill(0));
      return;
    }

    // Create audio context and analyser
    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.8;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    dataArrayRef.current = dataArray;

    audioContextRef.current = audioContext;
    analyserRef.current = analyser;

    // Get the audio stream from the track
    const stream = audioTrack.mediaStream;
    if (stream) {
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
    } else {
      // If stream is not available yet, wait for it
      const checkStream = setInterval(() => {
        const currentStream = audioTrack.mediaStream;
        if (currentStream) {
          const source = audioContext.createMediaStreamSource(currentStream);
          source.connect(analyser);
          clearInterval(checkStream);
        }
      }, 100);

      // Cleanup check interval after 5 seconds if still no stream
      setTimeout(() => {
        clearInterval(checkStream);
      }, 5000);
    }

    // Animation loop
    const updateLevels = () => {
      if (!analyserRef.current || !dataArrayRef.current) return;

      analyserRef.current.getByteFrequencyData(dataArrayRef.current);

      // Get average levels for each bar (divide frequency data into barCount groups)
      const samplesPerBar = Math.floor(dataArrayRef.current.length / barCount);
      const newLevels: number[] = [];

      for (let i = 0; i < barCount; i++) {
        let sum = 0;
        const start = i * samplesPerBar;
        const end = Math.min(start + samplesPerBar, dataArrayRef.current.length);

        for (let j = start; j < end; j++) {
          sum += dataArrayRef.current[j];
        }

        const avg = sum / (end - start);
        // Normalize to 0-1 range (0-255 -> 0-1)
        newLevels.push(avg / 255);
      }

      setAudioLevels(newLevels);
      animationFrameRef.current = requestAnimationFrame(updateLevels);
    };

    updateLevels();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close();
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

