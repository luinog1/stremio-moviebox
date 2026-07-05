"""
Stream Provider - Updated to preserve 4K streams and proper filtering
"""
import logging
from typing import List, Dict, Any, Optional
from moviebox.downloadables import MovieBoxClient, MovieBoxStream
import re

logger = logging.getLogger(__name__)

class StreamProcessor:
    """Process and filter streams from MovieBox"""
    
    # Resolution priority (higher number = better quality)
    RESOLUTION_PRIORITY = {
        "4k": 4,
        "2160p": 4,
        "1080p": 3,
        "720p": 2,
        "480p": 1,
        "360p": 0
    }
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.min_resolution = config.get("resolution", "all")
        self.language = config.get("language", "all")
        self.febox_cookie = config.get("febox_cookie")
        
        # Initialize MovieBox client with FEBOX cookie
        self.client = MovieBoxClient(febox_cookie=self.febox_cookie)
    
    async def get_streams(self, imdb_id: str, content_type: str = "movie") -> List[Dict[str, Any]]:
        """Get streams for a given IMDB ID"""
        logger.info(f"Fetching streams for {imdb_id} with config: {self.config}")
        
        # Get raw streams from MovieBox
        moviebox_streams = await self.client.search_content("", imdb_id)
        
        # Convert to Stremio format
        stremio_streams = []
        for stream in moviebox_streams:
            stremio_stream = self._convert_to_stremio_format(stream)
            if stremio_stream:
                stremio_streams.append(stremio_stream)
        
        # Apply filters
        filtered_streams = self._filter_streams(stremio_streams)
        
        # Sort by quality (highest first)
        sorted_streams = self._sort_by_quality(filtered_streams)
        
        logger.info(f"Returning {len(sorted_streams)} streams for {imdb_id}")
        return sorted_streams
    
    def _convert_to_stremio_format(self, stream: MovieBoxStream) -> Optional[Dict[str, Any]]:
        """Convert MovieBox stream to Stremio stream format"""
        # Determine quality tag for display
        quality_tag = self._get_quality_tag(stream.quality)
        
        # Build title with quality info
        title_parts = [stream.title]
        if quality_tag:
            title_parts.append(quality_tag)
        if stream.language:
            title_parts.append(stream.language)
        
        return {
            "name": "MovieBox",
            "title": " | ".join(title_parts),
            "url": stream.url,
            "quality": quality_tag,
            "isFree": True,
            "source": stream.source
        }
    
    def _get_quality_tag(self, quality: str) -> str:
        """Get standardized quality tag"""
        quality_lower = quality.lower()
        if "4k" in quality_lower or "2160" in quality_lower:
            return "4K"
        elif "1080" in quality_lower:
            return "1080p"
        elif "720" in quality_lower:
            return "720p"
        elif "480" in quality_lower:
            return "480p"
        else:
            return quality
    
    def _filter_streams(self, streams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter streams based on configuration"""
        filtered = []
        
        for stream in streams:
            # Check minimum resolution
            if not self._meets_min_resolution(stream.get("quality", "")):
                logger.debug(f"Filtered out stream due to resolution: {stream.get('quality')}")
                continue
            
            # Check language filter
            if not self._meets_language_filter(stream):
                logger.debug(f"Filtered out stream due to language: {stream.get('title')}")
                continue
            
            filtered.append(stream)
        
        logger.info(f"Filtered {len(streams)} streams to {len(filtered)}")
        return filtered
    
    def _meets_min_resolution(self, quality: str) -> bool:
        """Check if stream meets minimum resolution requirement"""
        if self.min_resolution == "all":
            return True
        
        quality_lower = quality.lower()
        stream_priority = self.RESOLUTION_PRIORITY.get(quality_lower, 0)
        min_priority = self.RESOLUTION_PRIORITY.get(self.min_resolution.lower(), 0)
        
        return stream_priority >= min_priority
    
    def _meets_language_filter(self, stream: Dict[str, Any]) -> bool:
        """Check if stream meets language filter"""
        if self.language == "all":
            return True
        
        title = stream.get("title", "").lower()
        language = self.language.lower()
        
        # Simple language check in title
        return language in title
    
    def _sort_by_quality(self, streams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort streams by quality (highest first)"""
        def get_priority(stream):
            quality = stream.get("quality", "").lower()
            return self.RESOLUTION_PRIORITY.get(quality, 0)
        
        return sorted(streams, key=get_priority, reverse=True)
