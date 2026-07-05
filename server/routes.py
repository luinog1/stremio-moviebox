import logging
import json
import base64
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from pathlib import Path
from streaming.provider import StreamProcessor

logger = logging.getLogger(__name__)

router = APIRouter()

# Configuração padrão caso o base64 falhe
DEFAULT_CONFIG = {
    "resolution": "all",
    "language": "all",
    "layout": "cinematic",
    "febox_cookie": None
}

@router.get("/", response_class=HTMLResponse)
async def root():
    """Redireciona para a página de configuração"""
    return RedirectResponse(url="/configure/")

@router.get("/configure/", response_class=HTMLResponse)
async def configure_page():
    """Serve a página de configuração HTML diretamente sem Jinja2"""
    html_file = Path("web/index.html")
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text())
    return HTMLResponse("<h1>Página de configuração não encontrada</h1>", status_code=404)

def decode_config(config_base64: str) -> dict:
    """Decodifica o base64 da URL de forma segura"""
    try:
        # Adiciona padding se necessário
        padded_base64 = config_base64 + '=' * (-len(config_base64) % 4)
        config_json = base64.urlsafe_b64decode(padded_base64).decode('utf-8')
        return json.loads(config_json)
    except Exception as e:
        logger.error(f"Erro ao decodificar config: {e}")
        return DEFAULT_CONFIG.copy()

@router.get("/{config_base64}/manifest.json")
async def get_manifest(config_base64: str):
    """Gera o manifest do addon"""
    config = decode_config(config_base64)
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
    """Obtém os streams para o conteúdo solicitado"""
    config = decode_config(config_base64)
    full_config = {**DEFAULT_CONFIG, **config}
    
    logger.info(f"Stream request: {imdb_id} with config: {full_config}")
    
    # Inicializa o processador com a configuração
    processor = StreamProcessor(full_config)
    
    # Busca os streams
    streams = await processor.get_streams(imdb_id, content_type)
    
    return {"streams": streams}
