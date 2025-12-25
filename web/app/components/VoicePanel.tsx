"use client";

import React, { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track, RemoteParticipant, Participant, ConnectionState, createLocalAudioTrack, ParticipantKind } from "livekit-client";
import type { LocalAudioTrack, RemoteAudioTrack } from "livekit-client";
import { useAppContext } from "../contexts/AppContext";
import MiniGraph from "./MiniGraph";
import { payloadToMiniGraphRows } from "../utils/voicePayloadToRows";
import AudioVisualizer from "./AudioVisualizer";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function VoicePanel() {
  const { voiceState, setVoiceState } = useAppContext();
  const roomRef = useRef<Room | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const micTrackRef = useRef<LocalAudioTrack | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>(ConnectionState.Disconnected);
  const [isMuted, setIsMuted] = useState(false);
  const [agentAudioTrack, setAgentAudioTrack] = useState<RemoteAudioTrack | null>(null);
  const [agentState, setAgentState] = useState<"initializing" | "listening" | "thinking" | "speaking">("initializing");
  const stateCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Generate unique room name
  const generateRoomName = () => {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 9);
    return `voice-${timestamp}-${random}`;
  };

  // Request LiveKit token from backend
  const requestToken = async (roomName: string, userIdentity: string = "user"): Promise<{ token: string; url: string }> => {
    const response = await fetch(`${API_URL}/voice/token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        room_name: roomName,
        user_identity: userIdentity,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Failed to get token" }));
      throw new Error(error.detail || "Failed to get LiveKit token");
    }

    return response.json();
  };

  // Connect to LiveKit room
  const connectToRoom = async () => {
    if (roomRef.current?.state === ConnectionState.Connected) {
      return; // Already connected
    }

    try {
      setVoiceState({ error: null });
      setConnectionState(ConnectionState.Connecting);

      const roomName = generateRoomName();
      const { token, url } = await requestToken(roomName, "user");

      // Create room and connect
      const room = new Room();
      roomRef.current = room;

      // Set up event handlers
      room.on(RoomEvent.Connected, () => {
        console.log("Connected to LiveKit room");
        setConnectionState(ConnectionState.Connected);
        setVoiceState({
          isConnected: true,
          roomName,
          error: null,
        });
      });

      room.on(RoomEvent.Disconnected, (reason) => {
        console.log("Disconnected from LiveKit room", reason);
        setConnectionState(ConnectionState.Disconnected);
        setVoiceState({
          isConnected: false,
          isListening: false,
          isAgentSpeaking: false,
          roomName: null,
        });
        cleanup();
      });

      room.on(RoomEvent.Reconnecting, () => {
        console.log("Reconnecting to LiveKit room");
        setConnectionState(ConnectionState.Reconnecting);
      });

      room.on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
        console.log("Participant connected", participant.identity, "kind", participant.kind);
        
        // Check if this is the agent participant
        if (participant.kind === ParticipantKind.Agent) {
          // Get agent state from attributes
          const stateAttr = participant.attributes?.get("lk.agent.state");
          if (stateAttr) {
            setAgentState(stateAttr as "initializing" | "listening" | "thinking" | "speaking");
          }

          // Listen for state changes via attribute updates
          // Note: LiveKit AgentSession updates lk.agent.state attribute
          // Poll periodically to detect state changes
          if (stateCheckIntervalRef.current) {
            clearInterval(stateCheckIntervalRef.current);
          }
          stateCheckIntervalRef.current = setInterval(() => {
            const newState = participant.attributes?.get("lk.agent.state");
            if (newState) {
              setAgentState((prev) => {
                if (prev !== newState) {
                  return newState as "initializing" | "listening" | "thinking" | "speaking";
                }
                return prev;
              });
            }
          }, 500);

          // Get agent audio track
          participant.audioTracks.forEach((publication) => {
            if (publication.track) {
              attachAudioTrack(publication.track);
              setAgentAudioTrack(publication.track as RemoteAudioTrack);
            }
          });

          // Listen for new tracks from agent
          participant.on("trackSubscribed", (track: Track) => {
            if (track.kind === "audio") {
              attachAudioTrack(track);
              setAgentAudioTrack(track as RemoteAudioTrack);
            }
          });
        }
      });

      room.on(RoomEvent.TrackSubscribed, (track: Track, _publication: any, participant: Participant) => {
        console.log("Track subscribed from participant", participant.identity, "kind", track.kind);
        if (track.kind === "audio" && participant.kind === ParticipantKind.Agent) {
          attachAudioTrack(track);
          setAgentAudioTrack(track as RemoteAudioTrack);
        }
      });

      // Listen for data channel messages (tool results, transcripts)
      room.on(RoomEvent.DataReceived, (payload: Uint8Array, participant: Participant | undefined, kind: string | undefined, topic: string | undefined) => {
        try {
          const text = new TextDecoder().decode(payload);
          const data = JSON.parse(text);
          
          // Handle tool result (all statuses, including no_results, needs_clarification, etc.)
          if (data.status) {
            setVoiceState({
              toolResult: data,
            });
            
            // Add to history
            const historyEntry = {
              timestamp: Date.now(),
              userTranscript: voiceState.userTranscript || "",
              agentResponse: voiceState.agentResponse || "",
              toolResult: data,
            };
            setVoiceState((prev) => ({
              connectionHistory: [...(prev.connectionHistory || []), historyEntry],
            }));
          }
          
          // Handle transcript updates
          if (data.transcript) {
            setVoiceState({ userTranscript: data.transcript });
          }
          
          // Handle agent response
          if (data.response) {
            setVoiceState({ agentResponse: data.response });
          }
        } catch (error) {
          console.error("Error parsing data channel message:", error);
        }
      });

      // Connect to room
      await room.connect(url, token);

      // Check for existing agent participants
      room.remoteParticipants.forEach((participant) => {
        if (participant.kind === ParticipantKind.Agent) {
          const stateAttr = participant.attributes?.get("lk.agent.state");
          if (stateAttr) {
            setAgentState(stateAttr as "initializing" | "listening" | "thinking" | "speaking");
          }
          
          // Get existing audio tracks
          participant.audioTracks.forEach((publication) => {
            if (publication.track) {
              attachAudioTrack(publication.track);
              setAgentAudioTrack(publication.track as RemoteAudioTrack);
            }
          });
        }
      });

      // Start audio playback (required by browsers for autoplayed audio)
      try {
        await room.startAudio();
      } catch (audioError) {
        console.warn("Failed to start room audio automatically:", audioError);
      }

      // Request microphone permission and publish audio
      try {
        const micTrack = await createLocalAudioTrack();
        micTrackRef.current = micTrack;
        await room.localParticipant.publishTrack(micTrack);
        setVoiceState({ isListening: true });
      } catch (micError: any) {
        console.error("Microphone error:", micError);
        if (micError.name === "NotAllowedError" || micError.name === "PermissionDeniedError") {
          setVoiceState({
            error: "Microphone access denied. Please enable microphone permissions in your browser.",
          });
        } else {
          setVoiceState({
            error: `Microphone error: ${micError.message}`,
          });
        }
      }

      // Set up audio element for agent audio playback
      if (!audioElementRef.current) {
        const audioElement = document.createElement("audio");
        audioElement.autoplay = true;
        audioElement.playsInline = true;
        audioElement.volume = 1.0;
        audioElementRef.current = audioElement;
        document.body.appendChild(audioElement);
        
        // Try to play immediately (required by browsers for autoplay)
        audioElement.play().catch((err) => {
          console.warn("Initial audio play failed (may need user interaction):", err);
        });
      } else {
        // Ensure existing audio element is ready
        audioElementRef.current.volume = 1.0;
      }
    } catch (error: any) {
      console.error("Connection error:", error);
      setConnectionState(ConnectionState.Disconnected);
      setVoiceState({
        isConnected: false,
        error: error.message || "Failed to connect to voice agent",
      });
      cleanup();
    }
  };

  // Attach audio track to audio element
  const attachAudioTrack = (track: Track) => {
    if (!audioElementRef.current) {
      console.warn("Audio element not ready, cannot attach track");
      return;
    }
    
    if (track.kind !== "audio") {
      return;
    }
    
    console.log("Attaching audio track", track.sid, "state:", track.state);
    
    try {
      // Attach the track to the audio element
      track.attach(audioElementRef.current);
      
      // Ensure audio element plays (required by browsers)
      const playPromise = audioElementRef.current.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          console.warn("Failed to play audio element:", err);
        });
      }
      
      setVoiceState({ isAgentSpeaking: true });
      
      // Detect when track stops or is muted
      track.on("ended", () => {
        console.log("Audio track ended");
        setVoiceState({ isAgentSpeaking: false });
      });
      
      track.on("muted", () => {
        console.log("Audio track muted");
        setVoiceState({ isAgentSpeaking: false });
      });
      
      track.on("unmuted", () => {
        console.log("Audio track unmuted");
        setVoiceState({ isAgentSpeaking: true });
        // Try to play again when unmuted
        if (audioElementRef.current) {
          audioElementRef.current.play().catch((err) => {
            console.warn("Failed to play audio after unmute:", err);
          });
        }
      });
      
      console.log("Successfully attached audio track");
    } catch (error) {
      console.error("Error attaching audio track:", error);
    }
  };

  // Disconnect from room
  const disconnectFromRoom = async () => {
    if (roomRef.current) {
      await roomRef.current.disconnect();
    }
    cleanup();
  };

  // Cleanup resources
  const cleanup = () => {
    if (stateCheckIntervalRef.current) {
      clearInterval(stateCheckIntervalRef.current);
      stateCheckIntervalRef.current = null;
    }
    if (micTrackRef.current) {
      micTrackRef.current.stop();
      micTrackRef.current = null;
    }
    if (audioElementRef.current) {
      audioElementRef.current.remove();
      audioElementRef.current = null;
    }
    setAgentAudioTrack(null);
    setAgentState("initializing");
    roomRef.current = null;
  };

  // Toggle microphone mute
  const toggleMute = () => {
    if (micTrackRef.current) {
      if (isMuted) {
        micTrackRef.current.unmute();
      } else {
        micTrackRef.current.mute();
      }
      setIsMuted(!isMuted);
    }
  };

  // Handle connect/disconnect button click
  const handleToggleConnection = () => {
    if (connectionState === ConnectionState.Connected) {
      disconnectFromRoom();
    } else {
      connectToRoom();
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []);

  // Get MiniGraph rows from tool result
  const graphRows = voiceState.toolResult?.status === "ok" && voiceState.toolResult.payload
    ? payloadToMiniGraphRows(voiceState.toolResult.payload)
    : [];

  const hasGraphData = graphRows.length > 0;
  const showPlaceholder = voiceState.toolResult?.status === "ok" && 
    voiceState.toolResult.payload &&
    graphRows.length === 0 &&
    (voiceState.toolResult.payload.intent === "gene_overview_query" ||
     voiceState.toolResult.payload.intent === "disease_therapies_query");

  const hasResponseContent = voiceState.agentResponse || voiceState.toolResult?.message;
  const hasQuestion = voiceState.userTranscript;

  // Helper functions for state-based styling
  const getStateColor = (state: string, connState: ConnectionState): string => {
    if (connState === ConnectionState.Connecting || connState === ConnectionState.Reconnecting) {
      return "#f59e0b"; // Amber
    }
    if (connState !== ConnectionState.Connected) {
      return "var(--text-2)"; // Gray
    }
    switch (state) {
      case "listening":
        return "#10b981"; // Green
      case "speaking":
        return "#3b82f6"; // Blue
      case "thinking":
        return "#8b5cf6"; // Purple
      default:
        return "var(--accent)";
    }
  };

  const getButtonClass = (connState: ConnectionState, state: string): string => {
    if (connState === ConnectionState.Connected) {
      if (state === "listening") return "voice-button-listening";
      if (state === "speaking") return "voice-button-speaking";
      if (state === "thinking") return "voice-button-thinking";
      return "voice-button-connected";
    }
    return "voice-button-disconnected";
  };

  const getStatusText = (connState: ConnectionState, state: string): string => {
    if (connState === ConnectionState.Connecting) return "Connecting...";
    if (connState === ConnectionState.Reconnecting) return "Reconnecting...";
    if (connState !== ConnectionState.Connected) return "Ready to Start";
    
    switch (state) {
      case "listening":
        return "Listening";
      case "speaking":
        return "Agent Speaking";
      case "thinking":
        return "Thinking...";
      case "initializing":
        return "Connected";
      default:
        return "Connected";
    }
  };

  return (
    <div className="graph-panel">
      <div className="panel-header">
        <h3 className="panel-title">Voice Agent</h3>
      </div>
      <div className="panel-content">
        {/* Row 1: Centered Hero Voice Controls */}
        <div className="layout-row">
          <div className="layout-column full-width">
            <div className="card voice-hero-card">
              <div className="card-content" style={{ padding: "40px 20px", display: "flex", flexDirection: "column", alignItems: "center", gap: "24px" }}>
                {/* Hero Button with Pulsing Ring */}
                <div className="voice-hero-container">
                  {/* Pulsing Ring */}
                  {connectionState === ConnectionState.Connected && (
                    <div 
                      className={`voice-pulse-ring ${agentState === "listening" ? "pulse-active" : ""} ${agentState === "speaking" ? "pulse-speaking" : ""}`}
                      style={{
                        position: "absolute",
                        width: "120px",
                        height: "120px",
                        borderRadius: "50%",
                        border: `2px solid ${getStateColor(agentState, connectionState)}`,
                        opacity: 0.6,
                        animation: connectionState === ConnectionState.Connected ? "pulse-ring 2s ease-in-out infinite" : "none",
                      }}
                    />
                  )}
                  
                  {/* Main Button */}
                  <button
                    onClick={handleToggleConnection}
                    disabled={connectionState === ConnectionState.Connecting || connectionState === ConnectionState.Reconnecting}
                    className={`voice-hero-button ${getButtonClass(connectionState, agentState)}`}
                    style={{
                      width: "100px",
                      height: "100px",
                      borderRadius: "50%",
                      border: "none",
                      cursor: connectionState === ConnectionState.Connecting || connectionState === ConnectionState.Reconnecting ? "not-allowed" : "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "32px",
                      position: "relative",
                      zIndex: 1,
                      transition: "all 0.3s ease",
                      boxShadow: connectionState === ConnectionState.Connected 
                        ? `0 0 20px ${getStateColor(agentState, connectionState)}40, 0 4px 12px rgba(0,0,0,0.15)`
                        : "0 4px 12px rgba(0,0,0,0.15)",
                    }}
                  >
                    {connectionState === ConnectionState.Connecting && "⏳"}
                    {connectionState === ConnectionState.Reconnecting && "🔄"}
                    {connectionState === ConnectionState.Connected && (agentState === "speaking" ? "🔊" : "🎤")}
                    {connectionState === ConnectionState.Disconnected && "▶️"}
                  </button>
                </div>

                {/* Status Text */}
                <div style={{ textAlign: "center" }}>
                  <div 
                    className="voice-status-text"
                    style={{
                      fontSize: "16px",
                      fontWeight: "600",
                      color: getStateColor(agentState, connectionState),
                      marginBottom: "8px",
                    }}
                  >
                    {getStatusText(connectionState, agentState)}
                  </div>
                  {connectionState === ConnectionState.Connected && (
                    <div style={{ display: "flex", gap: "16px", justifyContent: "center", alignItems: "center", fontSize: "14px", color: "var(--text-2)" }}>
                      <button
                        onClick={toggleMute}
                        className={`button ${isMuted ? "button-secondary" : "button-primary"}`}
                        style={{ padding: "6px 12px", fontSize: "12px" }}
                        title={isMuted ? "Unmute microphone" : "Mute microphone"}
                      >
                        {isMuted ? "🔇 Unmute" : "🎤 Mute"}
                      </button>
                    </div>
                  )}
                </div>

                {/* Audio Visualizer */}
                {connectionState === ConnectionState.Connected && agentAudioTrack && (
                  <div style={{ width: "100%", maxWidth: "300px" }}>
                    <AudioVisualizer audioTrack={agentAudioTrack} barCount={7} />
                  </div>
                )}

                {/* Error Message */}
                {voiceState.error && (
                  <div
                    style={{
                      padding: "12px 16px",
                      backgroundColor: "rgba(239, 68, 68, 0.1)",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      borderRadius: "var(--radius)",
                      color: "#fca5a5",
                      fontSize: "14px",
                      textAlign: "center",
                      maxWidth: "400px",
                    }}
                  >
                    {voiceState.error}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Row 2: Response (if available) */}
        {voiceState.toolResult && hasResponseContent && (
          <div className="layout-row">
            <div className="layout-column full-width">
              <div className="card">
                <header className="panel-header">
                  <h3 className="panel-title">Response</h3>
                </header>
                <div className="card-content">
                  {hasQuestion && (
                    <p className="question-text">
                      <span className="question-label">Question</span>
                      {voiceState.userTranscript}
                    </p>
                  )}
                  <div className="answer-content">
                    {voiceState.agentResponse || voiceState.toolResult.message}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Row 3: Graph + Raw JSON (if results available) */}
        {voiceState.toolResult && (
          <div className="layout-row">
            <div className="layout-column subgraph-column">
              <div className="card">
                <header className="panel-header">
                  <h3 className="panel-title">Interactive Subgraph</h3>
                </header>
                <div className="card-content">
                  {showPlaceholder ? (
                    <div
                      style={{
                        padding: "40px",
                        textAlign: "center",
                        color: "var(--text-2)",
                        fontSize: "12px",
                      }}
                    >
                      Summary statistics only - no graph visualization available
                    </div>
                  ) : hasGraphData ? (
                    <div className="graph-shell">
                      <div className="graph-container">
                        <MiniGraph rows={graphRows} />
                      </div>
                    </div>
                  ) : (
                    <div
                      style={{
                        padding: "40px",
                        textAlign: "center",
                        color: "var(--text-2)",
                        fontSize: "12px",
                      }}
                    >
                      No graph data to visualize
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="layout-column answer-column">
              <div className="card">
                <header className="panel-header">
                  <h3 className="panel-title">Raw Results</h3>
                </header>
                <div className="card-content">
                  <pre className="value-json">
                    {JSON.stringify(voiceState.toolResult, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

