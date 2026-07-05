"""
MovieBox API Client - Updated with FEBOX cookie support and 4K resolution handling
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class MovieBoxStream(BaseModel):
    """Model for MovieBox stream data"""
    title: str
    url: str
    quality: str = "1080p"
    size: Optional[str] = None
    language: Optional[str] = None
    source: str = "moviebox"

class MovieBoxClient:
    """Client for MovieBox API with FEBOX cookie support"""
    
    def __init__(self, febox_cookie: Optional[str] = None):
        self.base_urls = {
            "v1": "https://api.moviebox.com/v1",
            "v2": "https://api.moviebox.com/v2", 
            "v3": "https://api.moviebox.com/v3"
        }
        self.febox_cookie = febox_cookie
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        # Add FEBOX cookie if provided
        if self.febox_cookie:
            self.cookies = {"FEBOX": self.febox_cookie}
            logger.info("FEBOX cookie configured for 4K access")
        else:
            self.cookies = {}
            logger.warning("No FEBOX cookie provided - 4K streams may not be available")
    
    async def search_content(self, query: str, imdb_id: str) -> List[MovieBoxStream]:
        """Search for content by IMDB ID"""
        streams = []
        
        # Try all API versions concurrently for maximum coverage
        tasks = [
            self._fetch_from_v1(imdb_id),
            self._fetch_from_v2(imdb_id),
            self._fetch_from_v3(imdb_id)  # v3 likely supports 4K
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"API error: {result}")
                continue
            if result:
                streams.extend(result)
        
        # Deduplicate streams by URL
        seen_urls = set()
        unique_streams = []
        for stream in streams:
            if stream.url not in seen_urls:
                seen_urls.add(stream.url)
                unique_streams.append(stream)
        
        logger.info(f"Found {len(unique_streams)} unique streams for {imdb_id}")
        return unique_streams
    
    async def _fetch_from_v1(self, imdb_id: str) -> List[MovieBoxStream]:
        """Fetch from legacy API v1"""
        url = f"{self.base_urls['v1']}/search"
        params = {"q": imdb_id, "type": "movie"}
        
        try:
            async with httpx.AsyncClient(cookies=self.cookies, headers=self.headers) as client:
                response = await client.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                streams = []
                for item in data.get("results", []):
                    # Parse stream data - include all resolutions
                    stream = MovieBoxStream(
                        title=item.get("title", "Unknown"),
                        url=item.get("stream_url", ""),
                        quality=self._extract_quality(item),
                        size=item.get("size"),
                        language=item.get("language"),
                        source="moviebox_v1"
                    )
                    if stream.url:
                        streams.append(stream)
                
                return streams
        except Exception as e:
            logger.error(f"V1 API error: {e}")
            return []
    
    async def _fetch_from_v2(self, imdb_id: str) -> List[MovieBoxStream]:
        """Fetch from web API v2"""
        url = f"{self.base_urls['v2']}/content"
        params = {"imdb_id": imdb_id}
        
        try:
            async with httpx.AsyncClient(cookies=self.cookies, headers=self.headers) as client:
                response = await client.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                streams = []
                for item in data.get("streams", []):
                    # Include all resolutions - no filtering here
                    stream = MovieBoxStream(
                        title=data.get("title", "Unknown"),
                        url=item.get("url", ""),
                        quality=item.get("quality", "1080p"),
                        size=item.get("size"),
                        language=item.get("audio"),
                        source="moviebox_v2"
                    )
                    if stream.url:
                        streams.append(stream)
                
                return streams
        except Exception as e:
            logger.error(f"V2 API error: {e}")
            return []
    
    async def _fetch_from_v3(self, imdb_id: str) -> List[MovieBoxStream]:
        """Fetch from mobile API v3 - likely supports 4K with FEBOX cookie"""
        url = f"{self.base_urls['v3']}/movie"
        params = {"imdb": imdb_id, "quality": "all"}  # Request all qualities
        
        try:
            async with httpx.AsyncClient(cookies=self.cookies, headers=self.headers) as client:
                response = await client.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                streams = []
                for item in data.get("data", {}).get("streams", []):
                    # Explicitly check for 4K/2160p streams
                    quality = item.get("quality", "1080p")
                    stream = MovieBoxStream(
                        title=data.get("data", {}).get("title", "Unknown"),
                        url=item.get("url", ""),
                        quality=quality,
                        size=item.get("size"),
                        language=item.get("language"),
                        source="moviebox_v3"
                    )
                    
                    # Log 4K streams for debugging
                    if "4k" in quality.lower() or "2160" in quality:
                        logger.info(f"Found 4K stream: {stream.url}")
                    
                    if stream.url:
                        streams.append(stream)
                
                return streams
        except Exception as e:
            logger.error(f"V3 API error: {e}")
            return []
    
    def _extract_quality(self, item: Dict[str, Any]) -> str:
        """Extract quality from stream item"""
        # Check multiple possible quality fields
        quality = item.get("quality", "")
        if not quality:
            quality = item.get("resolution", "1080p")
        
        # Normalize quality strings
        quality_lower = quality.lower()
        if "4k" in quality_lower or "2160" in quality_lower:
            return "4K"
        elif "1080" in quality_lower:
            return "1080p"
        elif "720" in quality_lower:
            return "720p"
        else:
            return quality
