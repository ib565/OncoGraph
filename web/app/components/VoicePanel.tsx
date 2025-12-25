"use client";

import React, { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track, RemoteParticipant, Participant, ConnectionState, createLocalAudioTrack } from "livekit-client";
import type { LocalAudioTrack } from "livekit-client";
import { useAppContext } from "../contexts/AppContext";
import MiniGraph from "./MiniGraph";
import { payloadToMiniGraphRows } from "../utils/voicePayloadToRows";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function VoicePanel() {
  const { voiceState, setVoiceState } = useAppContext();
  const roomRef = useRef<Room | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const micTrackRef = useRef<LocalAudioTrack | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>(ConnectionState.Disconnected);
  const [isMuted, setIsMuted] = useState(false);

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
        console.log("Participant connected", participant.identity);
        // Attach any remote audio tracks (in this app, the only remote participant is the agent)
        participant.audioTracks.forEach((publication) => {
          if (publication.track) {
            attachAudioTrack(publication.track);
          }
        });

        // Listen for new tracks from this participant
        participant.on("trackSubscribed", (track: Track) => {
          if (track.kind === "audio") {
            attachAudioTrack(track);
          }
        });
      });

      room.on(RoomEvent.TrackSubscribed, (track: Track, _publication: any, participant: Participant) => {
        console.log("Track subscribed from participant", participant.identity, "kind", track.kind);
        if (track.kind === "audio") {
          attachAudioTrack(track);
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
        audioElementRef.current = audioElement;
        document.body.appendChild(audioElement);
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
    if (audioElementRef.current && track.kind === "audio") {
      track.attach(audioElementRef.current);
      setVoiceState({ isAgentSpeaking: true });
      
      // Detect when track stops
      track.on("ended", () => {
        setVoiceState({ isAgentSpeaking: false });
      });
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
    if (micTrackRef.current) {
      micTrackRef.current.stop();
      micTrackRef.current = null;
    }
    if (audioElementRef.current) {
      audioElementRef.current.remove();
      audioElementRef.current = null;
    }
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

  return (
    <div className="voice-panel">
      {/* Voice Controls */}
      <div className="card">
        <header className="panel-header">
          <h3 className="panel-title">Voice Agent</h3>
        </header>
        <div className="card-content">
          <div style={{ display: "flex", gap: "12px", alignItems: "center", marginBottom: "16px" }}>
            <button
              onClick={handleToggleConnection}
              disabled={connectionState === ConnectionState.Connecting || connectionState === ConnectionState.Reconnecting}
              className={`button ${connectionState === ConnectionState.Connected ? "button-danger" : "button-primary"}`}
              style={{ minWidth: "120px" }}
            >
              {connectionState === ConnectionState.Connecting && "Connecting..."}
              {connectionState === ConnectionState.Reconnecting && "Reconnecting..."}
              {connectionState === ConnectionState.Connected && "Disconnect"}
              {connectionState === ConnectionState.Disconnected && "Start Voice"}
            </button>

            {connectionState === ConnectionState.Connected && (
              <button
                onClick={toggleMute}
                className={`button ${isMuted ? "button-secondary" : "button-primary"}`}
                title={isMuted ? "Unmute microphone" : "Mute microphone"}
              >
                {isMuted ? "🔇 Unmute" : "🎤 Mute"}
              </button>
            )}

            <div style={{ flex: 1 }}>
              {connectionState === ConnectionState.Connected && (
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      backgroundColor: voiceState.isListening ? "#10b981" : "#6b7280",
                      display: "inline-block",
                    }}
                  />
                  <span style={{ fontSize: "14px", color: "#6b7280" }}>
                    {voiceState.isListening ? "Listening" : "Not listening"}
                  </span>
                  {voiceState.isAgentSpeaking && (
                    <>
                      <span
                        style={{
                          width: "8px",
                          height: "8px",
                          borderRadius: "50%",
                          backgroundColor: "#3b82f6",
                          display: "inline-block",
                          marginLeft: "12px",
                        }}
                      />
                      <span style={{ fontSize: "14px", color: "#6b7280" }}>Agent speaking</span>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>

          {voiceState.error && (
            <div
              style={{
                padding: "12px",
                backgroundColor: "#fee2e2",
                border: "1px solid #fecaca",
                borderRadius: "4px",
                color: "#991b1b",
                marginBottom: "16px",
              }}
            >
              {voiceState.error}
            </div>
          )}

          {voiceState.userTranscript && (
            <div style={{ marginBottom: "8px" }}>
              <strong>You:</strong> {voiceState.userTranscript}
            </div>
          )}

          {voiceState.agentResponse && (
            <div style={{ marginBottom: "8px" }}>
              <strong>Agent:</strong> {voiceState.agentResponse}
            </div>
          )}
        </div>
      </div>

      {/* Agent Response & Results */}
      {voiceState.toolResult && (
        <>
          {/* Agent Response Card */}
          <div className="card" style={{ marginTop: "16px" }}>
            <header className="panel-header">
              <h3 className="panel-title">Response</h3>
            </header>
            <div className="card-content">
              {voiceState.userTranscript && (
                <p className="question-text">
                  <span className="question-label">Question</span>
                  {voiceState.userTranscript}
                </p>
              )}
              <div className="answer-content">
                {voiceState.agentResponse || voiceState.toolResult.message || "No response"}
              </div>
            </div>
          </div>

          {/* Results: Graph + Raw JSON */}
          <div className="layout-row" style={{ marginTop: "16px" }}>
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
                        color: "#6b7280",
                        backgroundColor: "#f9fafb",
                        borderRadius: "4px",
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
                        color: "#6b7280",
                        backgroundColor: "#f9fafb",
                        borderRadius: "4px",
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
                  <pre
                    style={{
                      padding: "12px",
                      backgroundColor: "#f9fafb",
                      borderRadius: "4px",
                      overflow: "auto",
                      fontSize: "12px",
                      maxHeight: "400px",
                    }}
                  >
                    {JSON.stringify(voiceState.toolResult, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

