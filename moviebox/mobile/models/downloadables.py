from pydantic import BaseModel
from typing import List, Optional

class DownloadableFile(BaseModel):
    """
    Model for a single downloadable file/stream from MovieBox.
    """
    url: str
    quality: str = "1080p"
    size: Optional[str] = None
    language: Optional[str] = None
    source: str = "moviebox"

class RootDownloadableFilesDetailModel(BaseModel):
    """
    Root model containing a list of downloadable files.
    """
    title: str
    files: List[DownloadableFile]

class MovieBoxClient:
    """
    Original MovieBox API Client (placeholder for the original implementation).
    In the original code, this class would contain the methods to fetch data from the APIs.
    """
    pass
