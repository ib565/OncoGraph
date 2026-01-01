# OncoGraph Voice Agent Architecture

High-level system architecture diagram. For detailed component descriptions, performance targets, and query types, see [README.md](README.md).

## System Architecture

The voice agent uses a two-tier architecture: a **Fast-Path Query Engine** for sub-2-second graph queries, and a **Conversational Agent** that handles voice I/O and natural language generation.

<div style="max-height: 600px; overflow: auto; border: 1px solid #e1e4e8; border-radius: 6px; padding: 10px;">

```mermaid
graph TD
    subgraph "User"
        U((👤 User))
    end

    subgraph "Frontend Layer"
        WEB[Web Frontend<br/>Next.js + LiveKit Client]
        API[FastAPI Backend<br/>Token Generation]
    end

    subgraph "LiveKit Cloud"
        SFU(LiveKit SFU<br/>Real-time Media Server)
    end

    subgraph "Voice Agent Server"
        direction TB
        STT{{Deepgram STT<br/>Nova-3-Medical}}
        CONV{{Conversational LLM<br/>Gemini Flash Lite}}
        TTS{{Cartesia TTS<br/>Sonic-3}}
        
        subgraph "Fast-Path Query Engine"
            direction LR
            ROUTER[Router<br/>Intent Classification]
            ENTITY[(Canonical Entity Index)]
            TEMPLATE[Template Engine<br/>Cypher + Payload]
            NEO4J_EXEC[Neo4j Executor]
        end
        
        TOOL{oncograph_query Tool}
    end

    subgraph "Data Layer"
        NEO4J[(OncoGraph Knowledge Graph)]
    end

    %% User interactions
    U -->|Speech| WEB
    WEB -->|Audio Stream| SFU
    SFU -->|Audio| STT
    STT -->|Transcript| CONV
    
    %% Conversational flow
    CONV -->|Tool Call| TOOL
    TOOL -->|Query| ROUTER
    
    %% Fast-path flow
    ROUTER -->|Extract Entities| ENTITY
    ENTITY -->|Normalized</br>Entities| ROUTER
    ROUTER -->|Intent + Entities| TEMPLATE
    TEMPLATE -->|Cypher Query| NEO4J_EXEC
    NEO4J_EXEC -->|Query| NEO4J
    NEO4J -->|Results| NEO4J_EXEC
    NEO4J_EXEC -->|Raw Results| TEMPLATE
    TEMPLATE -->|Structured Payload| TOOL
    TOOL -->|OncoGraphToolResult| CONV
    
    %% Response flow
    CONV -->|Natural Language| TTS
    TTS -->|Audio Stream| SFU
    SFU -->|Audio| WEB
    WEB -->|Response| U
    
    %% Token generation
    WEB -->|Request Token| API
    API -->|LiveKit Token| WEB
    
    %% Styling
    classDef user fill:#fff9c4,stroke:#f57f17,stroke-width:3px
    classDef frontend fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef livekit fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef aiModel fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef tool fill:#ffebee,stroke:#c62828,stroke-width:3px
    classDef fastpath fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef entityIndex fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    classDef database fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    
    class U user
    class WEB,API frontend
    class SFU livekit
    class STT,CONV,TTS aiModel
    class TOOL tool
    class ROUTER,TEMPLATE,NEO4J_EXEC fastpath
    class ENTITY entityIndex
    class NEO4J database
```

</div>

## Key Flow

1. **User speech** → Frontend → LiveKit Cloud → STT
2. **STT transcript** → Conversational LLM
3. **If graph query** → `oncograph_query` tool → Fast-Path Engine
4. **Fast-Path**: Router → Entity Index (normalize) → Template → Neo4j → Structured payload
5. **Tool result** → Conversational LLM → Natural language response
6. **Response** → TTS → LiveKit → Frontend → User

For implementation details, see [README.md](README.md).

