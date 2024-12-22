# youtube/src/youtube/tools/research_tool.py

import asyncio
from typing import Any, Dict, List, Callable
import json
import logging
from dataclasses import asdict
from colorama import Fore, Style, init
init()  # Initialize colorama

from ..core.research import ResearchManager, VideoMetadata
from ..core.youtube_api import YouTubeAPI
from ..core.prompts import PromptTemplates

logger = logging.getLogger(__name__)

class ResearchTool:
    def __init__(self, youtube_api: YouTubeAPI):
        self.youtube_api = youtube_api
        self.research_manager = ResearchManager()
        self.current_query_id = None

    async def _format_progress(self, stage: str, detail: str, emoji: str = "🔍") -> None:
        """Format and log progress updates."""
        border = "─" * 50
        message = f"{Fore.BLUE}{emoji} {stage}{Style.RESET_ALL}: {detail}"
        logger.info(f"\n{border}\n{message}\n{border}")

    async def execute_research(
        self,
        topic: str,
        session: Any,
        progress_callback: Callable = None
    ) -> Dict[str, Any]:
        """Execute the full research workflow."""
        try:
            # Initialize research session
            self.current_query_id = f"research_{hash(topic)}"
            state = self.research_manager.start_research(self.current_query_id, topic)
            
            # Step 1: Generate initial search terms
            await self._format_progress("Starting Research", f"Topic: {topic}", "🎯")
            
            initial_terms_resp = await session.create_message(
                messages=[{
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": PromptTemplates.initial_search_terms(topic)
                    }
                }],
                max_tokens=500
            )
            
            # Parse the response text
            search_config = json.loads(initial_terms_resp.content.text)
            state.search_terms.extend([
                search_config["search_term_1"],
                search_config["search_term_2"]
            ])
            
            await self._format_progress(
                "Initial Search Terms",
                f"Generated: {', '.join(state.search_terms)}",
                "🔍"
            )

            # Begin iterative research process
            for iteration in range(1, state.max_iterations + 1):
                await self._format_progress(
                    f"Research Iteration {iteration}/{state.max_iterations}",
                    f"Processing search terms...",
                    "🔄"
                )

                # Fetch and process videos for current search terms
                current_terms = state.search_terms[-2:]  # Get last two terms
                video_summaries = []
                
                for term in current_terms:
                    # Search videos
                    videos = await self.youtube_api.search_videos(
                        term,
                        progress_callback=progress_callback
                    )
                    
                    for video in videos:
                        if video.video_id not in state.processed_videos:
                            transcript = await self.youtube_api.get_transcript(video.video_id)
                            if not transcript:
                                continue
                            
                            comments = await self.youtube_api.get_comments(video.video_id)
                            
                            await self.research_manager.add_video_content(
                                self.current_query_id,
                                video,
                                transcript
                            )
                            
                            summary_resp = await session.create_message(
                                messages=[{
                                    "role": "user",
                                    "content": {
                                        "type": "text",
                                        "text": PromptTemplates.format_video_summary(
                                            asdict(video),
                                            transcript,
                                            comments
                                        )
                                    }
                                }], 
                                max_token=900
                            )
                            video_summaries.append(
                                json.loads(summary_resp.content.text)
                            )
                
                # Assess progress and plan next steps
                assessment_resp = await session.create_message(
                    messages=[{
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": PromptTemplates.assess_content(
                                topic,
                                state.current_outline or "No outline yet",
                                iteration,
                                state.max_iterations,
                                state.search_terms,
                                video_summaries
                            )
                        }
                    }],
                    max_tokens=900
                )
                
                assessment = json.loads(assessment_resp.content.text)
                state.current_outline = assessment["outline_updates"]
                
                await self._format_progress(
                    "Progress Assessment",
                    assessment["assessment"],
                    "📊"
                )
                
                # Add new search terms for next iteration
                if iteration < state.max_iterations:
                    state.search_terms.extend([
                        assessment["search_term_1"],
                        assessment["search_term_2"]
                    ])
                    await self._format_progress(
                        "Next Search Terms",
                        f"Generated: {assessment['search_term_1']}, {assessment['search_term_2']}",
                        "🎯"
                    )

            # Generate final report
            await self._format_progress(
                "Generating Final Report",
                "Retrieving relevant content...",
                "📝"
            )
            
            # For each section in the final outline, retrieve relevant chunks
            outline_sections = state.current_outline.split('\n')
            all_relevant_chunks = []
            
            for section in outline_sections:
                if section.strip():
                    chunks = await self.research_manager.retrieve_relevant_chunks(
                        self.current_query_id,
                        section,
                        k=5
                    )
                    all_relevant_chunks.extend(map(asdict, chunks))
            
            # Generate final report
            report_resp = await session.create_message(
                messages=[{
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": PromptTemplates.generate_final_report(
                            topic,
                            state.current_outline,
                            all_relevant_chunks,
                            {v.video_id: asdict(v) for v in state.processed_videos.values()}
                        )
                    }
                }], max_tokens=2000
            )
            
            final_report = report_resp.content.text
            
            # Cleanup
            self.research_manager.cleanup_research(self.current_query_id)
            
            await self._format_progress(
                "Research Complete",
                f"Processed {len(state.processed_videos)} videos",
                "✨"
            )
            
            return {"report": final_report}

        except Exception as e:
            logger.error(f"Error in research execution: {str(e)}")
            if self.current_query_id:
                self.research_manager.cleanup_research(self.current_query_id)
            raise