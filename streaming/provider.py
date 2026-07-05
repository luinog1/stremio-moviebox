import logging
import asyncio
from typing import List, Dict, Any, Optional
from moviebox.mobile.models.downloadables import RootDownloadableFilesDetailModel, DownloadableFile
from moviebox.mobile.main import MobileClient  # Assumindo que este é o cliente principal da pasta mobile
import httpx

logger = logging.getLogger(__name__)

class StreamProcessor:
    """Processa e filtra streams do MovieBox com suporte a 4K e FEBOX Cookie"""
    
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
        
    async def get_streams(self, imdb_id: str, content_type: str = "movie") -> List[Dict[str, Any]]:
        """Obtém os streams para o conteúdo solicitado"""
        logger.info(f"Buscando streams para {imdb_id} com config: {self.config}")
        
        streams_data = []
        
        try:
            # Inicializa o cliente mobile original do repositório
            client = MobileClient()
            
            # Se houver cookie FEBOX, configuramos no cliente para liberar o 4K
            if self.febox_cookie:
                client.session.cookies.set("FEBOX", self.febox_cookie)
                logger.info("FEBOX cookie configurado para acesso 4K")
            
            # Busca o conteúdo (este método varia conforme a base original, geralmente usa imdb_id ou tmdb_id)
            # Assumindo que client.get_downloadables retorna um modelo compatível
            downloadables = await client.get_downloadables(imdb_id=imdb_id)
            
            # Extrai os streams
            for item in downloadables.files:
                quality = self._extract_quality(item)
                stream = {
                    "title": f"{downloadables.title} | {quality} | {item.language or 'Unknown'}",
                    "url": item.url,
                    "quality": quality,
                    "isFree": True,
                    "source": "moviebox"
                }
                streams_data.append(stream)
                
        except Exception as e:
            logger.error(f"Erro ao buscar streams do MovieBox: {e}")
        
        # Aplica os filtros de resolução e idioma
        filtered_streams = self._filter_streams(streams_data)
        sorted_streams = self._sort_by_quality(filtered_streams)
        
        logger.info(f"Retornando {len(sorted_streams)} streams para {imdb_id}")
        return sorted_streams
    
    def _extract_quality(self, item) -> str:
        """Extrai a resolução do stream"""
        # Verifica múltiplos campos possíveis onde a qualidade pode estar
        quality = getattr(item, 'quality', '') or getattr(item, 'resolution', '') or "1080p"
        quality_lower = quality.lower()
        
        if "4k" in quality_lower or "2160" in quality_lower:
            return "4K"
        elif "1080" in quality_lower:
            return "1080p"
        elif "720" in quality_lower:
            return "720p"
        elif "480" in quality_lower:
            return "480p"
        return quality
    
    def _filter_streams(self, streams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filtra streams baseado na configuração"""
        filtered = []
        
        for stream in streams:
            if not self._meets_min_resolution(stream.get("quality", "")):
                continue
            if not self._meets_language_filter(stream):
                continue
            filtered.append(stream)
        
        return filtered
    
    def _meets_min_resolution(self, quality: str) -> bool:
        if self.min_resolution == "all":
            return True
        
        quality_lower = quality.lower()
        stream_priority = self.RESOLUTION_PRIORITY.get(quality_lower, 0)
        min_priority = self.RESOLUTION_PRIORITY.get(self.min_resolution.lower(), 0)
        
        return stream_priority >= min_priority
    
    def _meets_language_filter(self, stream: Dict[str, Any]) -> bool:
        if self.language == "all":
            return True
        
        title = stream.get("title", "").lower()
        language = self.language.lower()
        return language in title
    
    def _sort_by_quality(self, streams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ordena streams por qualidade (maior primeiro)"""
        def get_priority(stream):
            quality = stream.get("quality", "").lower()
            return self.RESOLUTION_PRIORITY.get(quality, 0)
        
        return sorted(streams, key=get_priority, reverse=True)
