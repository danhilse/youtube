# youtube/src/youtube/server.py

import asyncio
import logging
import os
from dotenv import load_dotenv
import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp

from .core.youtube_api import YouTubeAPI
from .tools.research_tool import ResearchTool

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

class YouTubeMCPServer:
    def __init__(self):
        if not YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY environment variable is required")

        self.server = Server("youtube")
        self.youtube_api = YouTubeAPI(YOUTUBE_API_KEY)
        self.research_tool = ResearchTool(self.youtube_api)
        
        self._setup_handlers()

    def _setup_handlers(self):
        self.server.list_tools()(self._handle_list_tools)
        self.server.call_tool()(self._handle_call_tool)

    async def _handle_list_tools(self) -> list[types.Tool]:
        return [
            types.Tool(
                name="youtube-research",
                description="Search YouTube (Shorts under 1 min and long form 1-35 min) for a topic. Performs iterative, curiosity-driven research using transcripts and comments to create a comprehensive report.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Research topic or question"
                        },
                    },
                    "required": ["topic"],
                },
            )
        ]

    async def _handle_call_tool(
        self,
        name: str,
        arguments: dict | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        try:
            if name == "youtube-research":
                if not arguments or 'topic' not in arguments:
                    raise ValueError("Missing 'topic' argument")

                # This callback dispatches progress notifications, if the
                # current request context includes a `progressToken`.
                async def progress_callback(progress: float):
                    if hasattr(self.server.request_context.meta, 'progressToken'):
                        await self.server.request_context.session.send_notification(
                            "notifications/progress",
                            {
                                "progressToken": self.server.request_context.meta.progressToken,
                                "progress": progress,
                                "total": 1.0
                            }
                        )

                result = await self.research_tool.execute_research(
                    arguments['topic'],
                    self.server.request_context.session,
                    progress_callback=progress_callback
                )

                return [
                    types.TextContent(
                        type="text",
                        text=result["report"]
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

    async def run(self):
        logger.info("YouTube MCP server: entering run()")
        try:
            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                logger.info("YouTube MCP server: stdio transport established")
                # Removed the `progress=True` parameter
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="youtube",
                        server_version="0.1.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={},
                        ),
                    )
                )
        except Exception as e:
            logger.error("Error running server: %s", e, exc_info=True)
            raise
        finally:
            logger.info("YouTube MCP server: run() is exiting")

def main():
    server = YouTubeMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()