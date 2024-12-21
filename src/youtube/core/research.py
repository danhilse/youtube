# youtube/src/youtube/core/research.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import asyncio
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import logging

logger = logging.getLogger(__name__)

@dataclass
class VideoMetadata:
    video_id: str
    title: str
    description: str
    duration: int  # in seconds
    view_count: int
    channel_title: str
    publish_date: str

@dataclass
class TranscriptChunk:
    text: str
    video_id: str
    start_time: float
    end_time: float
    metadata: VideoMetadata

@dataclass
class ResearchState:
    query: str
    current_iteration: int = 1
    max_iterations: int = 3
    search_terms: List[str] = field(default_factory=list)
    processed_videos: Dict[str, VideoMetadata] = field(default_factory=dict)
    current_outline: Optional[str] = None
    
    # Embedding storage
    embeddings: Optional[faiss.IndexFlatL2] = None
    embedding_model: Optional[SentenceTransformer] = None
    chunks: List[TranscriptChunk] = field(default_factory=list)
    chunk_embeddings: List[np.ndarray] = field(default_factory=list)

class ResearchManager:
    def __init__(self):
        self._active_research: Dict[str, ResearchState] = {}
        self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

    def start_research(self, query_id: str, query: str) -> ResearchState:
        """Initialize a new research session."""
        if query_id in self._active_research:
            raise ValueError(f"Research session {query_id} already exists")
            
        state = ResearchState(
            query=query,
            embeddings=faiss.IndexFlatL2(384),  # 384 is the dimension for MiniLM-L6
            embedding_model=self._embedding_model
        )
        self._active_research[query_id] = state
        return state

    def get_research_state(self, query_id: str) -> ResearchState:
        """Get existing research state."""
        if query_id not in self._active_research:
            raise ValueError(f"No active research found for {query_id}")
        return self._active_research[query_id]

    async def add_video_content(
        self,
        query_id: str,
        video_metadata: VideoMetadata,
        transcript_text: str,
        chunk_size: int = 300,
        overlap: int = 50
    ):
        """Process and store video content with embeddings."""
        state = self.get_research_state(query_id)
        
        # Create overlapping chunks
        words = transcript_text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            
            # Create chunk with metadata
            chunk = TranscriptChunk(
                text=chunk_text,
                video_id=video_metadata.video_id,
                start_time=0,  # We'll need to calculate this from transcript data
                end_time=0,
                metadata=video_metadata
            )
            chunks.append(chunk)
            
            # Generate and store embedding
            embedding = self._embedding_model.encode([chunk_text])[0]
            state.embeddings.add(np.array([embedding]))
            state.chunks.append(chunk)
            state.chunk_embeddings.append(embedding)
            
        state.processed_videos[video_metadata.video_id] = video_metadata
        
        logger.info(
            f"Added {len(chunks)} chunks for video {video_metadata.video_id} "
            f"to research {query_id}"
        )

    async def retrieve_relevant_chunks(
        self,
        query_id: str,
        topic: str,
        k: int = 5
    ) -> List[TranscriptChunk]:
        """Retrieve most relevant chunks for a topic."""
        state = self.get_research_state(query_id)
        
        # Generate embedding for the topic
        query_embedding = self._embedding_model.encode([topic])[0]
        
        # Search for similar chunks
        distances, indices = state.embeddings.search(
            np.array([query_embedding]),
            k
        )
        
        # Return the relevant chunks
        return [state.chunks[i] for i in indices[0]]

    def cleanup_research(self, query_id: str):
        """Clean up research session."""
        if query_id in self._active_research:
            del self._active_research[query_id]