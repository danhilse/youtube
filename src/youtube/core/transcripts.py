# youtube/src/youtube/core/transcripts.py

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import logging
import asyncio
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

logger = logging.getLogger(__name__)

@dataclass
class TranscriptSegment:
    text: str
    start: float
    duration: float
    video_id: str

class TranscriptManager:
    def __init__(self):
        self.formatter = TextFormatter()

    async def get_transcript_segments(
        self,
        video_id: str,
        languages: List[str] = ['en']
    ) -> List[TranscriptSegment]:
        """Get transcript segments with timing information."""
        try:
            transcript_list = await asyncio.to_thread(
                YouTubeTranscriptApi.get_transcript,
                video_id,
                languages=languages
            )
            
            segments = []
            for item in transcript_list:
                segment = TranscriptSegment(
                    text=item['text'],
                    start=item['start'],
                    duration=item['duration'],
                    video_id=video_id
                )
                segments.append(segment)
                
            return segments
            
        except Exception as e:
            logger.error(f"Error getting transcript for {video_id}: {str(e)}")
            return []

    async def get_full_transcript(
        self,
        video_id: str,
        languages: List[str] = ['en']
    ) -> Optional[str]:
        """Get complete transcript text."""
        try:
            transcript_list = await asyncio.to_thread(
                YouTubeTranscriptApi.get_transcript,
                video_id,
                languages=languages
            )
            return self.formatter.format_transcript(transcript_list)
            
        except Exception as e:
            logger.error(f"Error getting full transcript for {video_id}: {str(e)}")
            return None

    def chunk_transcript(
        self,
        segments: List[TranscriptSegment],
        chunk_size: int = 300,
        overlap: int = 50
    ) -> List[TranscriptSegment]:
        """Chunk transcript into overlapping segments."""
        chunks = []
        current_chunk = []
        current_text_length = 0
        
        for segment in segments:
            words = segment.text.split()
            current_chunk.append(segment)
            current_text_length += len(words)
            
            if current_text_length >= chunk_size:
                # Create chunk
                combined_text = " ".join(seg.text for seg in current_chunk)
                start_time = current_chunk[0].start
                end_time = current_chunk[-1].start + current_chunk[-1].duration
                
                chunk = TranscriptSegment(
                    text=combined_text,
                    start=start_time,
                    duration=end_time - start_time,
                    video_id=segment.video_id
                )
                chunks.append(chunk)
                
                # Handle overlap
                overlap_segments = []
                overlap_length = 0
                for seg in reversed(current_chunk):
                    words = seg.text.split()
                    if overlap_length + len(words) > overlap:
                        break
                    overlap_segments.insert(0, seg)
                    overlap_length += len(words)
                    
                current_chunk = overlap_segments
                current_text_length = overlap_length
        
        # Add remaining segments as final chunk if any
        if current_chunk:
            combined_text = " ".join(seg.text for seg in current_chunk)
            start_time = current_chunk[0].start
            end_time = current_chunk[-1].start + current_chunk[-1].duration
            
            chunk = TranscriptSegment(
                text=combined_text,
                start=start_time,
                duration=end_time - start_time,
                video_id=segment.video_id
            )
            chunks.append(chunk)
        
        return chunks

    def clean_transcript(self, text: str) -> str:
        """Clean transcript text for better processing."""
        # Remove multiple spaces
        text = " ".join(text.split())
        
        # Remove common transcript artifacts
        artifacts = [
            "[Music]", "[Applause]", "[Laughter]",
            "[Background Noise]", "[Silence]"
        ]
        for artifact in artifacts:
            text = text.replace(artifact, "")
            
        return text.strip()

    async def process_transcript(
        self,
        video_id: str,
        chunk_size: int = 300,
        overlap: int = 50,
        languages: List[str] = ['en']
    ) -> List[TranscriptSegment]:
        """Complete transcript processing workflow."""
        segments = await self.get_transcript_segments(video_id, languages)
        if not segments:
            return []
            
        # Clean each segment
        for segment in segments:
            segment.text = self.clean_transcript(segment.text)
            
        # Chunk the segments
        chunks = self.chunk_transcript(segments, chunk_size, overlap)
        
        return chunks