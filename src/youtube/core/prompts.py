# youtube/src/youtube/core/prompts.py

from typing import List, Dict, Any
from dataclasses import dataclass
import json

@dataclass
class ModelConfig:
    """Configuration for different sampling needs."""
    RESEARCH_ASSESSMENT = {
        "modelPreferences": {
            "hints": [{"name": "claude-3-haiku"}],
            "speedPriority": 0.8,
            "costPriority": 0.7
        },
        "temperature": 0.7,
        "maxTokens": 1000
    }
    
    FINAL_REPORT = {
        "modelPreferences": {
            "hints": [{"name": "claude-3-sonnet"}],
            "intelligencePriority": 0.9
        },
        "temperature": 0.7,
        "maxTokens": 4000
    }

class PromptTemplates:
    """Collection of prompt templates for research workflow."""
    
    @staticmethod
    def initial_search_terms(query: str) -> Dict[str, Any]:
        """Generate prompt for initial search terms."""
        return {
            "messages": [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"""Given this research query: "{query}"

Based on your knowledge, generate TWO optimized YouTube search terms that will:
1. Cover different aspects or approaches to answering the query
2. Be likely to find high-quality, relevant content
3. Include any technical terms or specific phrases that would improve search results

Response format:
{{"search_term_1": "your first search term",
  "search_term_2": "your second search term",
  "rationale": "brief explanation of why you chose these terms"}}"""
                }
            }],
            **ModelConfig.RESEARCH_ASSESSMENT
        }

    @staticmethod
    def assess_content(
        query: str,
        current_outline: str,
        iteration: int,
        max_iterations: int,
        search_terms: List[str],
        video_summaries: List[str]
    ) -> Dict[str, Any]:
        """Generate prompt for assessing current knowledge and next steps."""
        return {
            "messages": [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"""Research Progress Assessment

Original Query: "{query}"

Current Iteration: {iteration}/{max_iterations}

Previous Search Terms: {json.dumps(search_terms, indent=2)}

Current Working Outline:
{current_outline}

Recent Video Summaries:
{json.dumps(video_summaries, indent=2)}

Based on our current knowledge and progress:

1. Assess what we've learned
2. Identify important knowledge gaps or areas needing deeper exploration
3. Generate TWO new search terms designed to:
   - Fill knowledge gaps
   - Explore interesting tangents relevant to the query
   - Find contrasting viewpoints if relevant
4. Propose improvements or additions to the working outline

Response format:
{{
  "assessment": "brief assessment of current knowledge",
  "gaps_identified": ["list of specific knowledge gaps"],
  "search_term_1": "first new search term",
  "search_term_2": "second new search term",
  "search_rationale": "explanation of new search terms",
  "outline_updates": "suggested changes to outline"
}}\n"""
                }
            }],
            **ModelConfig.RESEARCH_ASSESSMENT
        }

    @staticmethod
    def generate_final_report(
        query: str,
        final_outline: str,
        relevant_chunks: List[Dict],
        video_metadata: Dict
    ) -> Dict[str, Any]:
        """Generate prompt for final report creation."""
        return {
            "messages": [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f'''Research Report Generation

Original Query: "{query}"

Final Outline:
{final_outline}

Using the provided transcript chunks and metadata, create a comprehensive research report that:
1. Follows the outline structure
2. Incorporates relevant information from video transcripts
3. Cites specific videos and timestamps
4. Highlights differing perspectives and approaches
5. Includes a "Recommended Videos" section that explains which videos are most valuable for different aspects of the topic

Available Content:
{json.dumps(relevant_chunks, indent=2)}

Video Information:
{json.dumps(video_metadata, indent=2)}

Format the report in markdown with clear sections, citations, and proper formatting.'''
                }
            }],
            **ModelConfig.FINAL_REPORT
        }

    @staticmethod
    def format_video_summary(metadata: dict, transcript: str, comments: List[dict]) -> Dict[str, Any]:
        """Generate prompt for summarizing a single video's content."""
        return {
            "messages": [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"""Analyze this video content and provide a structured summary:

Video Metadata:
{json.dumps(metadata, indent=2)}

Transcript:
{transcript}

Top Comments:
{json.dumps(comments, indent=2)}

Provide a summary in this format:
{{
    "main_points": ["list of key points"],
    "unique_insights": ["specific insights this video adds"],
    "community_sentiment": "analysis of comment sentiment",
    "credibility_assessment": "brief assessment of video's credibility",
    "summary": "concise summary of video content"
}}"""
                }
            }],
            **ModelConfig.RESEARCH_ASSESSMENT
        }