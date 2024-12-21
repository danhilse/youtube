# youtube/src/youtube/core/youtube_api.py

import asyncio
from typing import List, Tuple, Dict, Optional, Callable, Any
from datetime import datetime, timezone
import logging
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
from datetime import datetime, timezone
from .research import VideoMetadata

logger = logging.getLogger(__name__)

class YouTubeAPI:
    def __init__(self, api_key: str):
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': True,
            'format': 'best'
        }

    async def search_videos(
        self,
        query: str,
        max_results: int = 7,  # 5 shorts + 2 long form
        progress_callback=None
    ) -> List[VideoMetadata]:
        """Search for videos and return metadata."""
        try:
            # First search for short videos (< 60s)
            shorts_request = self.youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=5,
                type='video',
                videoDuration='short',
                fields='items(id(videoId),snippet(title,description,channelTitle,publishedAt))'
            )
            shorts_response = await asyncio.to_thread(shorts_request.execute)

            # Then search for longer videos (1-35 min)
            long_request = self.youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=2,
                type='video',
                videoDuration='medium',
                fields='items(id(videoId),snippet(title,description,channelTitle,publishedAt))'
            )
            long_response = await asyncio.to_thread(long_request.execute)

            # Combine results
            all_items = shorts_response.get('items', []) + long_response.get('items', [])
            
            if progress_callback:
                await progress_callback(0.3)  # 30% progress after search

            # Get detailed video information
            video_ids = [item['id']['videoId'] for item in all_items]
            videos_request = self.youtube.videos().list(
                part='contentDetails,statistics',
                id=','.join(video_ids)
            )
            videos_response = await asyncio.to_thread(videos_request.execute)
            video_details = {
                item['id']: item 
                for item in videos_response['items']
            }

            if progress_callback:
                await progress_callback(0.5)  # 50% progress after details

            results = []
            for item in all_items:
                video_id = item['id']['videoId']
                if video_id in video_details:
                    details = video_details[video_id]
                    snippet = item['snippet']
                    
                    # Parse duration string to seconds
                    duration_str = details['contentDetails']['duration']
                    duration = self._parse_duration(duration_str)
                    
                    metadata = VideoMetadata(
                        video_id=video_id,
                        title=snippet['title'],
                        description=snippet['description'],
                        duration=duration,
                        view_count=int(details['statistics'].get('viewCount', 0)),
                        channel_title=snippet['channelTitle'],
                        publish_date=snippet['publishedAt']
                    )
                    results.append(metadata)

            return results

        except Exception as e:
            logger.error(f"Error searching videos: {str(e)}")
            raise

    async def get_transcript(
        self,
        video_id: str,
        languages=['en']
    ) -> Optional[str]:
        """Get video transcript."""
        try:
            transcript_list = await asyncio.to_thread(
                YouTubeTranscriptApi.get_transcript,
                video_id,
                languages=languages
            )
            
            # Combine transcript pieces
            full_transcript = ' '.join(
                item['text'] for item in transcript_list
            )
            
            return full_transcript

        except Exception as e:
            logger.error(f"Error getting transcript for {video_id}: {str(e)}")
            return None

    async def get_comments(
        self,
        video_id: str,
        max_comments: int = 100
    ) -> List[Dict]:
        """Get top comments for a video."""
        try:
            request = self.youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=max_comments,
                order='relevance',
                textFormat='plainText'
            )
            
            response = await asyncio.to_thread(request.execute)
            
            comments = []
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'text': comment['textDisplay'],
                    'author': comment['authorDisplayName'],
                    'likes': comment['likeCount'],
                    'publish_date': comment['publishedAt']
                })
                
            return comments

        except Exception as e:
            logger.error(f"Error getting comments for {video_id}: {str(e)}")
            return []

    def _parse_duration(self, duration_str: str) -> int:
        """Convert ISO 8601 duration to seconds."""
        hours = minutes = seconds = 0
        
        # Remove PT from start
        duration = duration_str[2:]
        
        # Extract hours, minutes, seconds
        time_str = duration.lower()
        
        # Find hours
        h_idx = time_str.find('h')
        if h_idx != -1:
            hours = int(time_str[:h_idx])
            time_str = time_str[h_idx + 1:]
            
        # Find minutes
        m_idx = time_str.find('m')
        if m_idx != -1:
            minutes = int(time_str[:m_idx])
            time_str = time_str[m_idx + 1:]
            
        # Find seconds
        s_idx = time_str.find('s')
        if s_idx != -1:
            seconds = int(time_str[:s_idx])
            
        return hours * 3600 + minutes * 60 + seconds