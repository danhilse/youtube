# youtube/src/youtube/core/report.py

from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass
import json
from .embeddings import EmbeddingsManager

logger = logging.getLogger(__name__)

@dataclass
class ReportSection:
    title: str
    content: List[Dict[str, Any]]  # List of relevant chunks with metadata

class ReportGenerator:
    def __init__(self, embeddings_manager: EmbeddingsManager):
        self.embeddings = embeddings_manager

    async def process_outline(
        self,
        outline: str,
    ) -> List[ReportSection]:
        """Process outline into sections with relevant content."""
        # Split outline into sections
        sections = []
        current_section = []
        
        for line in outline.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Check if line is a new section (starts with #)
            if line.startswith('#'):
                if current_section:
                    sections.append('\n'.join(current_section))
                current_section = [line]
            else:
                current_section.append(line)
                
        if current_section:
            sections.append('\n'.join(current_section))

        # Process each section
        processed_sections = []
        for section_text in sections:
            # Extract title (first line)
            lines = section_text.split('\n')
            title = lines[0].lstrip('#').strip()
            
            # Search for relevant content
            relevant_chunks = self.embeddings.search(
                section_text,
                k=5,
                threshold=0.6
            )
            
            section = ReportSection(
                title=title,
                content=relevant_chunks
            )
            processed_sections.append(section)
            
        return processed_sections

    def format_timestamp(self, seconds: float) -> str:
        """Format seconds into MM:SS format."""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def format_video_citation(
        self,
        video_id: str,
        start_time: float,
        metadata: Dict[str, Any]
    ) -> str:
        """Format video citation with title and timestamp."""
        timestamp = self.format_timestamp(start_time)
        title = metadata.get('title', 'Unknown Title')
        channel = metadata.get('channel_title', 'Unknown Channel')
        
        return f"[{title} by {channel} at {timestamp}](https://youtube.com/watch?v={video_id}&t={int(start_time)})"

    def generate_recommended_videos(
        self,
        processed_content: Dict[str, Any]
    ) -> str:
        """Generate recommended videos section."""
        videos = {}  # video_id -> metadata + citations
        
        # Collect video references
        for section in processed_content['sections']:
            for chunk in section.content:
                video_id = chunk['video_id']
                metadata = chunk.get('metadata', {})
                
                if video_id not in videos:
                    videos[video_id] = {
                        'metadata': metadata,
                        'citations': 0,
                        'sections': set(),
                        'similarity_sum': 0
                    }
                
                videos[video_id]['citations'] += 1
                videos[video_id]['sections'].add(section.title)
                videos[video_id]['similarity_sum'] += chunk.get('similarity', 0)
        
        # Sort videos by citations and average similarity
        sorted_videos = sorted(
            videos.items(),
            key=lambda x: (
                x[1]['citations'],
                x[1]['similarity_sum'] / x[1]['citations']
            ),
            reverse=True
        )
        
        # Format recommendations
        recommendations = []
        for video_id, info in sorted_videos:
            metadata = info['metadata']
            avg_similarity = info['similarity_sum'] / info['citations']
            sections = sorted(info['sections'])
            
            rec = (
                f"### {metadata.get('title', 'Unknown Title')}\n"
                f"- **Channel**: {metadata.get('channel_title', 'Unknown')}\n"
                f"- **Link**: https://youtube.com/watch?v={video_id}\n"
                f"- **Duration**: {self.format_timestamp(metadata.get('duration', 0))}\n"
                f"- **Relevance Score**: {avg_similarity:.2f}\n"
                f"- **Referenced In**: {', '.join(sections)}\n"
                f"- **Views**: {metadata.get('view_count', 'Unknown')}\n\n"
            )
            recommendations.append(rec)
            
        return "\n".join(recommendations)

    def format_markdown_report(
        self,
        topic: str,
        sections: List[ReportSection],
        processed_videos: Dict[str, Any]
    ) -> str:
        """Format final report in markdown."""
        report_parts = [
            f"# Research Report: {topic}\n\n"
        ]
        
        # Add table of contents
        report_parts.append("## Table of Contents\n")
        for i, section in enumerate(sections, 1):
            clean_title = section.title.strip().lower()
            link = clean_title.replace(' ', '-')
            report_parts.append(f"{i}. [{section.title}](#{link})\n")
        report_parts.append("\n")
        
        # Process each section
        for section in sections:
            report_parts.append(f"## {section.title}\n")
            
            # Group content by video
            video_content = {}
            for chunk in section.content:
                video_id = chunk['video_id']
                if video_id not in video_content:
                    video_content[video_id] = []
                video_content[video_id].append(chunk)
            
            # Format content with citations
            for video_id, chunks in video_content.items():
                for chunk in chunks:
                    # Add citation
                    citation = self.format_video_citation(
                        chunk['video_id'],
                        chunk['start_time'],
                        chunk['metadata']
                    )
                    
                    # Add formatted content
                    report_parts.append(f"{chunk['text']}\n\n")
                    report_parts.append(f"*Source: {citation}*\n\n")
            
            report_parts.append("\n")
        
        # Add recommended videos section
        report_parts.append("## Recommended Videos\n")
        report_parts.append("The following videos are recommended based on relevance and coverage:\n\n")
        report_parts.append(self.generate_recommended_videos({
            'sections': sections,
            'videos': processed_videos
        }))
        
        return "".join(report_parts)

    async def generate_report(
        self,
        topic: str,
        outline: str,
        session: Any
    ) -> str:
        """Complete report generation workflow."""
        try:
            # Process outline into sections with content
            sections = await self.process_outline(outline)
            
            # Get all processed videos
            video_ids = set()
            for section in sections:
                for chunk in section.content:
                    video_ids.add(chunk['video_id'])
            
            # Get metadata for all videos
            processed_videos = {
                video_id: self.embeddings.get_video_chunks(video_id)[0]['metadata']
                for video_id in video_ids
            }
            
            # Generate markdown report
            report = self.format_markdown_report(
                topic,
                sections,
                processed_videos
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise