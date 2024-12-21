# youtube/src/youtube/core/embeddings.py

from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import logging
from dataclasses import dataclass, asdict
from .transcripts import TranscriptSegment

logger = logging.getLogger(__name__)

@dataclass
class EmbeddedChunk:
    text: str
    video_id: str
    start_time: float
    end_time: float
    metadata: Dict[str, Any]
    embedding: Optional[np.ndarray] = None

class EmbeddingsManager:
    def __init__(self):
        # Initialize the embedding model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.dimension = 384  # Model output dimension
        
        # Initialize FAISS index
        self.index = None
        self.chunks: List[EmbeddedChunk] = []

    def initialize_index(self):
        """Initialize or reset the FAISS index."""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.chunks = []

    async def add_chunk(self, chunk: TranscriptSegment, metadata: Dict[str, Any]) -> None:
        """Add a transcript chunk to the index."""
        if self.index is None:
            self.initialize_index()

        # Generate embedding
        embedding = self.model.encode([chunk.text])[0]
        
        # Create embedded chunk
        embedded_chunk = EmbeddedChunk(
            text=chunk.text,
            video_id=chunk.video_id,
            start_time=chunk.start,
            end_time=chunk.start + chunk.duration,
            metadata=metadata,
            embedding=embedding
        )
        
        # Add to index and storage
        self.index.add(np.array([embedding]))
        self.chunks.append(embedded_chunk)
        
        logger.debug(
            f"Added chunk for video {chunk.video_id} "
            f"(time: {chunk.start:.1f}-{chunk.start + chunk.duration:.1f})"
        )

    async def add_chunks(
        self,
        chunks: List[TranscriptSegment],
        metadata: Dict[str, Any]
    ) -> None:
        """Add multiple chunks efficiently."""
        if self.index is None:
            self.initialize_index()

        # Generate embeddings for all chunks at once
        texts = [chunk.text for chunk in chunks]
        embeddings = self.model.encode(texts)
        
        # Add all embeddings to index
        self.index.add(embeddings)
        
        # Store chunks with embeddings
        for chunk, embedding in zip(chunks, embeddings):
            embedded_chunk = EmbeddedChunk(
                text=chunk.text,
                video_id=chunk.video_id,
                start_time=chunk.start,
                end_time=chunk.start + chunk.duration,
                metadata=metadata,
                embedding=embedding
            )
            self.chunks.append(embedded_chunk)
            
        logger.info(f"Added {len(chunks)} chunks to index")

    def search(
        self,
        query: str,
        k: int = 5,
        threshold: float = 0.75
    ) -> List[Dict[str, Any]]:
        """Search for most relevant chunks."""
        if self.index is None or not self.chunks:
            return []

        # Generate query embedding
        query_embedding = self.model.encode([query])[0]
        
        # Search index
        distances, indices = self.index.search(
            np.array([query_embedding]),
            k
        )
        
        results = []
        for distance, idx in zip(distances[0], indices[0]):
            # Convert distance to similarity score (0-1)
            similarity = 1 / (1 + distance)
            
            if similarity >= threshold:
                chunk = self.chunks[idx]
                result = {
                    "text": chunk.text,
                    "video_id": chunk.video_id,
                    "start_time": chunk.start_time,
                    "end_time": chunk.end_time,
                    "metadata": chunk.metadata,
                    "similarity": float(similarity)
                }
                results.append(result)
        
        return results

    def search_by_video(
        self,
        video_id: str,
        query: str,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search within a specific video's chunks."""
        # Get chunks for this video
        video_chunks = [
            chunk for chunk in self.chunks
            if chunk.video_id == video_id
        ]
        
        if not video_chunks:
            return []
            
        # Create temporary index for this video
        video_index = faiss.IndexFlatL2(self.dimension)
        embeddings = np.array([chunk.embedding for chunk in video_chunks])
        video_index.add(embeddings)
        
        # Search
        query_embedding = self.model.encode([query])[0]
        distances, indices = video_index.search(
            np.array([query_embedding]),
            min(k, len(video_chunks))
        )
        
        results = []
        for distance, idx in zip(distances[0], indices[0]):
            chunk = video_chunks[idx]
            similarity = 1 / (1 + distance)
            
            result = {
                "text": chunk.text,
                "video_id": chunk.video_id,
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "metadata": chunk.metadata,
                "similarity": float(similarity)
            }
            results.append(result)
        
        return results

    def get_video_chunks(self, video_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific video."""
        chunks = [
            asdict(chunk) for chunk in self.chunks
            if chunk.video_id == video_id
        ]
        return chunks

    def clear(self):
        """Clear the index and stored chunks."""
        self.initialize_index()
        self.chunks = []