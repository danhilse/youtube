# YouTube Research MCP Server

A Model Context Protocol (MCP) server that conducts intelligent, iterative research on YouTube topics. This server uses Claude's natural curiosity to explore topics deeply, collecting and analyzing information from both short-form and long-form content.

## Features

- **Intelligent Search Strategy**: Uses Claude to generate optimized search terms based on identified knowledge gaps and areas of interest
- **Comprehensive Content Analysis**: 
  - Processes both short (<60s) and long-form (1-35 min) videos
  - Analyzes transcripts, metadata, and top comments
  - Creates semantic embeddings for content retrieval
- **Iterative Research Process**:
  - Conducts multiple search passes
  - Each iteration improves understanding and coverage
  - Identifies and fills knowledge gaps
  - Explores relevant tangents and alternative viewpoints
- **Rich Final Reports**:
  - Well-structured markdown output
  - Section-specific content with video citations
  - Timestamped references to key points
  - Video recommendations with relevance explanations
  - Coverage analysis and alternative viewpoints

## Architecture

The server consists of several key components:

```
youtube/
└── src/
    └── youtube/
        ├── core/
        │   ├── embeddings.py     # Vector embeddings and similarity search
        │   ├── youtube_api.py    # YouTube API interactions
        │   ├── transcripts.py    # Transcript processing
        │   ├── prompts.py        # LLM prompt templates
        │   ├── research.py       # Research state management
        │   └── report.py         # Report generation
        ├── tools/
        │   └── research_tool.py  # MCP tool implementation
        ├── __init__.py
        └── server.py
```

### Component Overview

- **Research Manager**: Maintains research state, tracking progress and managing the iterative exploration process
- **YouTube API**: Handles video search, transcript fetching, and metadata retrieval
- **Embeddings**: Uses FAISS for efficient similarity search across video content
- **Report Generator**: Creates structured markdown reports with citations and recommendations

## Installation

1. **Prerequisites**:
   - Python 3.11 or higher
   - `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
   - YouTube Data API key (get one from [Google Cloud Console](https://console.cloud.google.com/))

2. **Setup**:
   ```bash
   # Clone the repository
   git clone [repository-url]
   cd youtube-research-mcp

   # Create and activate virtual environment
   uv venv
   source .venv/bin/activate  # On Unix/MacOS
   # or
   .venv\Scripts\activate     # On Windows

   # Install dependencies
   uv pip install -e .
   ```

3. **Configuration**:
   Create a `.env` file in the project root:
   ```env
   YOUTUBE_API_KEY=your_youtube_api_key_here
   ```

## Usage

### Running the Server

```bash
uv run youtube
```

### Using with Claude Desktop

1. Open your Claude Desktop configuration:
   ```bash
   code ~/Library/Application\ Support/Claude/claude_desktop_config.json  # MacOS
   # or
   code %AppData%\Claude\claude_desktop_config.json  # Windows
   ```

2. Add the server configuration:
   ```json
   {
     "mcpServers": {
       "youtube": {
         "command": "uv",
         "args": [
           "run",
           "youtube"
         ]
       }
     }
   }
   ```

3. Restart Claude Desktop

### Example Research Queries

```
Research how to make sourdough bread
```
```
Find different approaches to learning piano as an adult
```
```
Research the impact of intermittent fasting on athletic performance
```

### Understanding the Research Process

1. **Initial Search Terms**: Claude analyzes your query and generates two optimized search terms to begin the research.

2. **First Iteration**:
   - Fetches videos for both search terms
   - Processes transcripts and comments
   - Creates embeddings for semantic search
   - Assesses current knowledge
   - Identifies gaps and interesting angles
   - Generates new search terms

3. **Subsequent Iterations**:
   - Each iteration builds on previous knowledge
   - Explores new aspects or fills gaps
   - Updates the working outline
   - Integrates new information

4. **Final Report Generation**:
   - Creates structured markdown report
   - Uses semantic search to find relevant content
   - Includes citations with timestamps
   - Recommends most valuable videos

## Model Usage

The server uses two different Claude models:

- **Claude 3 Haiku**: For quick assessments and iterative planning
  - Analyzing current knowledge
  - Identifying gaps
  - Generating search terms
  - Processing video content

- **Claude 3 Sonnet**: For final report generation
  - Creating comprehensive summaries
  - Analyzing different viewpoints
  - Generating recommendations
  - Writing detailed explanations

## Development

### Directory Structure

```
youtube/
├── README.md
├── pyproject.toml
├── src/
│   └── youtube/
│       ├── core/           # Core functionality
│       ├── tools/          # MCP tool implementations
│       ├── __init__.py
│       └── server.py       # Main server implementation
└── tests/                  # Test suite (coming soon)
```

### Adding New Features

1. **New Functionality**:
   - Add core components in `src/youtube/core/`
   - Update tool implementations in `src/youtube/tools/`
   - Modify server.py as needed

2. **New Prompts**:
   - Add prompt templates to `core/prompts.py`
   - Include new prompt handlers in server implementation

### Running Tests (Coming Soon)

```bash
uv run pytest
```

## Troubleshooting

### Common Issues

1. **API Rate Limits**:
   - The server implements backoff strategies
   - Consider increasing wait times if hitting limits

2. **Missing Transcripts**:
   - Some videos may not have transcripts
   - Server will skip these and log warnings

3. **Memory Usage**:
   - FAISS index grows with processed videos
   - Each research session cleans up after completion

### Logs

Check the logs for detailed information:
```bash
tail -f ~/.local/share/youtube-research-mcp/logs/server.log
```

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) team for the protocol specification
- [Anthropic](https://anthropic.com/) for Claude integration
- [YouTube Data API](https://developers.google.com/youtube/v3) team

## Security

Please review our [security policy](SECURITY.md) for information about reporting vulnerabilities.