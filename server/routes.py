"""
FastAPI Routes - Updated to handle FEBOX cookie configuration
"""
import logging
import json
import base64
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from streaming.provider import StreamProcessor

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="web")

# Default configuration
DEFAULT_CONFIG = {
    "resolution": "all",
    "language": "all",
    "layout": "cinematic",
    "febox_cookie": None
}

@router.get("/", response_class=HTMLResponse)
async def root():
    """Redirect to configure page"""
    return RedirectResponse(url="/configure/")

@router.get("/configure/", response_class=HTMLResponse)
async def configure_page(request: Request):
    """Serve configuration page"""
    return templates.TemplateResponse("configure.html", {"request": request})

@router.get("/{config_base64}/manifest.json")
async def get_manifest(config_base64: str):
    """Generate addon manifest based on configuration"""
    try:
        # Decode configuration from base64
        config_json = base64.b64decode(config_base64).decode('utf-8')
        config = json.loads(config_json)
    except Exception as e:
        logger.error(f"Config decode error: {e}")
        config = DEFAULT_CONFIG
    
    # Merge with defaults
    full_config = {**DEFAULT_CONFIG, **config}
    
    manifest = {
        "id": "com.stremio.moviebox",
        "version": "1.0.0",
        "name": "MovieBox",
        "description": "Watch content from MovieBox in 4K, 1080p, and more",
        "types": ["movie", "series"],
        "catalogs": [],
        "resources": ["stream"],
        "idPrefixes": ["tt"],
        "behaviorHints": {
            "configurable": True,
            "configurationRequired": False
        }
    }
    
    return manifest

@router.get("/{config_base64}/stream/{content_type}/{imdb_id}.json")
async def get_stream(config_base64: str, content_type: str, imdb_id: str):
    """Get streams for content"""
    try:
        # Decode configuration from base64
        config_json = base64.b64decode(config_base64).decode('utf-8')
        config = json.loads(config_json)
    except Exception as e:
        logger.error(f"Config decode error: {e}")
        config = DEFAULT_CONFIG
    
    # Merge with defaults
    full_config = {**DEFAULT_CONFIG, **config}
    
    logger.info(f"Stream request: {imdb_id} with config: {full_config}")
    
    # Initialize stream processor with configuration
    processor = StreamProcessor(full_config)
    
    # Get streams
    streams = await processor.get_streams(imdb_id, content_type)
    
    return {"streams": streams}

@router.post("/configure/save")
async def save_configuration(request: Request):
    """Save configuration and return install URL"""
    try:
        data = await request.json()
        
        # Build configuration object
        config = {
            "resolution": data.get("resolution", "all"),
            "language": data.get("language", "all"),
            "layout": data.get("layout", "cinematic"),
            "febox_cookie": data.get("febox_cookie")
        }
        
        # Encode configuration to base64
        config_json = json.dumps(config)
        config_base64 = base64.b64encode(config_json.encode()).decode()
        
        # Generate install URL
        install_url = f"{request.base_url}{config_base64}/manifest.json"
        
        return {"install_url": install_url}
    
    except Exception as e:
        logger.error(f"Config save error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
