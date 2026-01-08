graph TD
    %% Define styles
    classDef data fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1;
    classDef process fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20;
    classDef storage fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#bf360c;
    classDef model fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;
    classDef user fill:#fffde7,stroke:#fbc02d,stroke-width:2px,stroke-dasharray: 5 5,color:#f57f17;

    %% --- PHASE 1: DATA PREPARATION & INDEXING ---
    subgraph "Phase 1: Data Prep & Indexing (Cells 1-4)"
        InputJSON[("cpa_anchored.json")]:::data
        SplitProc[/"Process: parent_child()"<br/>Split sections vs atomic units/]:::\process

        InputJSON --> SplitProc

        subgraph "Parent Track (Context Store)"
            ParentDocs[("Parent Documents<br/>(Full Original Content)")]:::data
            ParentStore[("Parent Lookup Store<br/>(Dict: ID -> Full Text)")]:::storage
        end

        subgraph "Child Track (Search Index)"
            ChildDocs[("Child Documents<br/>(Small Enriched Units)")]:::data
            EmbedModel(/"Embedding Model<br/>(HuggingFace: BAAI/bge-m3)"/):::model
            ChromaDB[("Chroma Vector DB<br/>(Collection: cpa_legal_index)")]:::storage
            BM25(/"BM25 Retriever<br/>(Keyword Index)"/):::process
        end

        SplitProc -- "Extracts full sections" --> ParentDocs
        SplitProc -- "Extracts atomic units" --> ChildDocs

        %% Indexing Children
        ChildDocs -- "Normalize & Embed" --> EmbedModel
        EmbedModel --> ChromaDB
        ChildDocs --> BM25

        %% Preparing Parent Lookup (Happens in Cell 5 conceptually)
        ParentDocs -.-> |"Load into memory for lookup"| ParentStore
    end

    %% --- PHASE 2: RETRIEVAL ---
    subgraph "Phase 2: Hybrid Retrieval Flow (Cell 5)"
        UserQ[/"👤 User Query Input"/]:::user
        Ensemble[/"Ensemble Retriever<br/>(Hybrid Search)"/]:::\process
        ChromaRet(/"Chroma Retriever<br/>(Vector Search k=5)"/):::process

        UserQ --> Ensemble
        Ensemble -- "Weight: 0.5" --> BM25
        Ensemble -- "Weight: 0.5" --> ChromaRet
        ChromaDB --> ChromaRet

        RetrievedChildren[("Retrieved Relevant<br/>CHILD Documents")]:::data
        BM25 --> RetrievedChildren
        ChromaRet --> RetrievedChildren

        IDLookup[/"Process: Metadata Lookup & Deduplication<br/>(Find Parent ID from Child)"/]:::\process
        RetrievedChildren --> IDLookup
        ParentStore --> |"Retrieve Full Text using ID"| IDLookup

        FinalContext[("Final Consolidated Context<br/>(Unique PARENT Full Texts)")]:::data
        IDLookup --> FinalContext
    end

    %% --- PHASE 3: GENERATION ---
    subgraph "Phase 3: Generation (Cells 6-10)"
        PromptTemp[/"Chat Prompt Template<br/>(Lawyer Persona)"/]:::\process
        GeminiLLM(/"Google Gemini LLM<br/>(gemini-2.5-flash, temp=0.3)"/):::model
        OutputParser(/"StrOutputParser"/]:::\process
        FinalAnswer[/"✅ Final Generated Answer"/]:::data

        UserQ -.-> |"Pass Question"| PromptTemp
        FinalContext --> |"Pass Formatted Context"| PromptTemp
        PromptTemp --> GeminiLLM
        GeminiLLM --> OutputParser
        OutputParser --> FinalAnswer
    end

    %% Check Cell 5 for ParentStore recreation
    InputJSON -.-> |"Re-read for lookup dict (Cell 5)"| ParentStore