import asyncio
import os
import logging
import json
import re
import yt_dlp

from googleapiclient.discovery import build
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from functools import partial
from concurrent.futures import ThreadPoolExecutor

import aiohttp

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

from pydantic import AnyUrl

# Set up logging (to stderr)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a thread pool executor for running blocking operations
thread_pool = ThreadPoolExecutor(max_workers=10)

# Create an MCP server instance
server = Server("youtube")

# Load environment variables
load_dotenv()
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

def safe_json_serialize(data):
    """Safely serialize data to JSON for debugging if needed."""
    try:
        return json.dumps(data)
    except (TypeError, ValueError) as e:
        logger.error(f"Error serializing data to JSON: {str(e)}")
        return json.dumps({"error": "Serialization error"})


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="youtube-search-terms",
            description="Generate specialized search terms for a YouTube topic",
            arguments=[
                types.PromptArgument(
                    name="topic",
                    description="Topic or query for which to generate search terms",
                    required=True,
                )
            ],
        )
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str,
    arguments: dict[str, str] | None
) -> types.GetPromptResult:
    if name != "youtube-search-terms":
        raise ValueError(f"Unknown prompt: {name}")

    if not arguments or "topic" not in arguments:
        raise ValueError("Missing argument 'topic' for youtube-search-terms prompt")

    topic = arguments["topic"]

    user_text = f"""
Analyze this research topic: "{topic}"

Generate 5 YouTube search terms that will collectively provide comprehensive coverage of this subject.
Consider:
1. Different aspects/angles
2. Various skill levels (beginner to advanced)
3. Specific techniques or methods
4. Common problems or challenges
5. Expert perspectives and critiques

Format your response as a simple list of 5 search terms, one per line.
Do not use generic terms like "tutorial" or "review" unless specifically relevant.
"""
    return types.GetPromptResult(
        description="Prompt to generate specialized YouTube search terms",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text=user_text.strip()),
            )
        ],
    )

async def fetch_search_terms_via_prompt(topic: str) -> list[str]:
    try:
        get_prompt_resp = await server.request_context.session.send_request(
            "prompts/get",
            {
                "name": "youtube-search-terms",
                "arguments": {"topic": topic}
            }
        )

        sampling_req = {
            "messages": get_prompt_resp["messages"],
            "maxTokens": 300
        }

        sampling_resp = await server.request_context.session.send_request(
            "sampling/createMessage",
            sampling_req
        )

        text_out = ""
        if isinstance(sampling_resp, dict):
            text_out = sampling_resp.get("content", {}).get("text", "")
        elif isinstance(sampling_resp, str):
            text_out = sampling_resp.strip()

        if not text_out:
            logger.warning("No text returned for search terms; fallback to basic terms.")
            return [topic, f"{topic} tutorial"]

        lines = [line.strip() for line in text_out.split("\n") if line.strip()]
        return lines[:5] if lines else [topic, f"{topic} tutorial"]

    except Exception as e:
        logger.error(f"fetch_search_terms_via_prompt error: {e}")
        # fallback
        return [topic, f"{topic} tutorial"]

async def youtube_search(youtube, query: str, videoDuration: str = "any", maxResults=10) -> list[str]:
    # A helper function to do a single search call
    # videoDuration can be "short", "medium", "long", or "any"
    # We'll get up to maxResults video IDs
    request = youtube.search().list(
        q=query,
        part='id',
        maxResults=maxResults,
        type='video',
        videoDuration=videoDuration
    )
    response = await asyncio.get_event_loop().run_in_executor(
        thread_pool, request.execute
    )
    return [item['id']['videoId'] for item in response.get('items', [])]

async def get_video_info(video_id: str) -> dict:
    ydl_opts = {'quiet': True}

    async def extract_info():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return await asyncio.get_event_loop().run_in_executor(
                thread_pool,
                partial(
                    ydl.extract_info,
                    f"https://www.youtube.com/watch?v={video_id}",
                    download=False
                )
            )

    try:
        info = await extract_info()
        return {
            'title': info.get('title', 'N/A'),
            'url': f"https://www.youtube.com/watch?v={video_id}",
            'description': info.get('description', 'N/A'),
            'duration': info.get('duration', 0)  # duration in seconds
        }
    except Exception as e:
        logger.error(f"Error fetching info for video {video_id}: {str(e)}")
        return {'duration': 0}

async def get_captions(video_id: str) -> str:
    async def fetch_transcript():
        return await asyncio.get_event_loop().run_in_executor(
            thread_pool, partial(YouTubeTranscriptApi.get_transcript, video_id)
        )

    try:
        transcript = await fetch_transcript()
        return " ".join([entry['text'] for entry in transcript])
    except Exception as e:
        logger.error(f"Error fetching captions for video {video_id}: {str(e)}")
        return "N/A"

async def handle_youtube_research(topic: str, progress_callback=None) -> tuple[list[dict], list[str]]:
    """
    Steps:
    1) Get search terms via prompt-based sampling.
    2) From those search terms:
       - Find short-form candidates (videoDuration=short) and filter top 5 under 1 minute.
       - Find long-form candidates (videoDuration=any) and filter top 2-3 between 1 and 30 minutes.
    3) Fetch metadata & captions for chosen videos.
    """
    try:
        search_terms = await fetch_search_terms_via_prompt(topic)
        if progress_callback:
            await progress_callback(0.1)

        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

        # We'll just take the first search term and use it for both short and long queries
        # or we can combine? Let's try using the first search term for simplicity:
        main_term = search_terms[0] if search_terms else topic

        # 2.1) Short-form: under 1 minute => use videoDuration=short
        # We'll fetch up to 10 short candidates and then filter by actual duration < 60s
        short_candidates = await youtube_search(youtube, main_term, videoDuration="short", maxResults=10)

        # get info for them
        short_info_tasks = [get_video_info(vid) for vid in short_candidates]
        short_infos = await asyncio.gather(*short_info_tasks)

        # filter top 5 with duration < 60s
        short_filtered = [i for i in short_infos if i.get('duration', 0) < 60]
        short_filtered = short_filtered[:5]

        if progress_callback:
            await progress_callback(0.4)

        # 2.2) Long-form: between 1 and 35 min => videoDuration=any and then filter by 60-1800s
        # We'll fetch up to 10 candidates and filter
        long_candidates = await youtube_search(youtube, main_term, videoDuration="any", maxResults=10)
        long_info_tasks = [get_video_info(vid) for vid in long_candidates]
        long_infos = await asyncio.gather(*long_info_tasks)

        # filter top 2-3 with duration between 60 and 1800s
        long_filtered = [i for i in long_infos if 60 <= i.get('duration', 0) <= 2100]
        long_filtered = long_filtered[:3]

        if progress_callback:
            await progress_callback(0.6)

        # Combine chosen videos
        chosen_videos = short_filtered + long_filtered

        # Now fetch captions for chosen videos
        async def fetch_captions_for(info):
            vid_id = info['url'].split('v=')[1]
            caps = await get_captions(vid_id)
            return {
                "info": info,
                "captions": caps
            }

        tasks = [fetch_captions_for(i) for i in chosen_videos]
        results = await asyncio.gather(*tasks)

        if progress_callback:
            await progress_callback(1.0)

        return results, search_terms

    except Exception as e:
        logger.error(f"Error in handle_youtube_research: {str(e)}")
        # fallback: no results
        return [], [topic, f"{topic} tutorial"]

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="youtube-research",
            description="Search YouTube (Shorts under 1 min and long form 1-35 min) for a topic",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                },
                "required": ["topic"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    try:
        if name == "youtube-research":
            if not arguments or 'topic' not in arguments:
                raise ValueError("Missing 'topic' argument.")

            async def progress_callback(progress: float):
                if hasattr(server.request_context.meta, 'progressToken'):
                    await server.request_context.session.send_notification(
                        "notifications/progress",
                        {
                            "progressToken": server.request_context.meta.progressToken,
                            "progress": progress,
                            "total": 1.0
                        }
                    )

            topic = arguments['topic']
            results, search_terms = await handle_youtube_research(topic, progress_callback=progress_callback)

            formatted = []
            formatted.append("Search Terms Used:\n" + "\n".join(search_terms) + "\n")
            formatted.append("Top 5 Videos Under 1 Minute + 2-3 Videos (1-5 min):\n")
            for r in results:
                info = r.get('info', {})
                title = info.get('title', 'N/A')
                url = info.get('url', 'N/A')
                duration = info.get('duration', 0)
                mins = duration // 60
                secs = duration % 60
                duration_str = f"{mins}m{secs}s"
                captions = r.get('captions', 'N/A')
                formatted.append(
                    f"Title: {title}\nURL: {url}\nDuration: {duration_str}\nCaptions: {captions}"
                )

            return [
                types.TextContent(
                    type="text",
                    text="\n\n".join(formatted)
                )
            ]
        else:
            raise ValueError(f"Unknown tool name: {name}")

    except Exception as e:
        logger.error(f"Error in handle_call_tool: {str(e)}")
        return [
            types.TextContent(
                type="text",
                text=f"Error executing tool '{name}': {str(e)}"
            )
        ]

async def main():
    logger.info("YouTube MCP server: entering main()")
    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            logger.info("YouTube MCP server: stdio transport established, calling server.run()")
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="youtube",
                    server_version="0.1.0",
                    capabilities={
                        "tools": {"listChanged": True},
                        "resources": {},
                        "prompts": {"listChanged": True},
                        "sampling": {}
                    }
                )
            )
            logger.info("YouTube MCP server: server.run() returned, finishing main()")
    except Exception as e:
        logger.error("Error running server: %s", e, exc_info=True)
    finally:
        logger.info("YouTube MCP server: main() is exiting")