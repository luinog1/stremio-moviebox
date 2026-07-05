"""
FebBox provider — porta Python do ShowboxAPI.js + FebBoxApi.js.

Fluxo:
  1. ShowBox API  → busca título → pega showbox_id + box_type
  2. ShowBox API  → share_link   → pega febbox_share_key
  3. FebBox API   → file_share_list (com cookie ui=<token>)
  4. FebBox API   → video_quality_list por fid → links directos (4K/HDR incluído)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any

import httpx
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────────────────
# ShowBox API config (idêntico ao ShowboxAPI.js)
# ─────────────────────────────────────────────────────────────────────────────
_SB_BASE_URL = "https://mbpapi.shegu.net/api/api_client/index/"
_SB_APP_KEY = "moviebox"
_SB_APP_ID = "com.tdo.showbox"
_SB_IV = "wEiphTn!"
_SB_KEY = "123d6cedf626dy54233aa1w6"
_SB_DEFAULTS: dict[str, str] = {
    "child_mode": "0",
    "app_version": "11.5",
    "lang": "en",
    "platform": "android",
    "channel": "Website",
    "appid": "27",
    "version": "129",
    "medium": "Website",
}

# FebBox base URL
_FB_BASE = "https://www.febbox.com"

# ─────────────────────────────────────────────────────────────────────────────
# Crypto helpers  (porta do CryptoJS.TripleDES + MD5 usado no JS)
# ─────────────────────────────────────────────────────────────────────────────

def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def _triple_des_encrypt(data: str, key: bytes, iv: bytes) -> str:
    """
    TripleDES CBC encrypt, PKCS5 padding — devolve base64 igual ao CryptoJS.
    Usa apenas stdlib + pycryptodome se disponível; fallback puro-Python via pyDes.
    """
    from Crypto.Cipher import DES3
    from Crypto.Util.Padding import pad

    padded = pad(data.encode("utf-8"), 8)  # DES block size = 8
    cipher = DES3.new(key, DES3.MODE_CBC, iv)
    return base64.b64encode(cipher.encrypt(padded)).decode()


def _sb_encrypt(payload: str) -> str:
    key = _SB_KEY.encode("utf-8")
    iv = _SB_IV.encode("utf-8")
    return _triple_des_encrypt(payload, key, iv)


def _sb_verify(encrypted: str) -> str:
    inner = _md5(_SB_APP_KEY) + _SB_KEY + encrypted
    return _md5(inner)


def _nanoid(length: int = 32) -> str:
    alphabet = "0123456789abcdef"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ─────────────────────────────────────────────────────────────────────────────
# ShowBox API
# ─────────────────────────────────────────────────────────────────────────────

def _build_sb_form(module: str, extra: dict) -> dict[str, str]:
    payload = {
        **_SB_DEFAULTS,
        "expired_date": str(int(time.time()) + 60 * 60 * 12),
        "module": module,
        **{k: str(v) for k, v in extra.items()},
    }
    encrypted = _sb_encrypt(json.dumps(payload))
    body_obj = {
        "app_key": _md5(_SB_APP_KEY),
        "verify": _sb_verify(encrypted),
        "encrypt_data": encrypted,
    }
    body_b64 = base64.b64encode(json.dumps(body_obj).encode()).decode()
    return {
        "data": body_b64,
        "appid": _SB_DEFAULTS["appid"],
        "platform": _SB_DEFAULTS["platform"],
        "version": _SB_DEFAULTS["version"],
        "medium": _SB_DEFAULTS["medium"],
    }


_SB_HEADERS = {
    "Platform": "android",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "okhttp/3.2.0",
}

_FB_HEADERS = {
    "x-requested-with": "XMLHttpRequest",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
}


async def _sb_request(
    client: httpx.AsyncClient, module: str, extra: dict
) -> dict:
    form = _build_sb_form(module, extra)
    # Append random token suffix exactly like the JS does
    body = "&".join(f"{k}={v}" for k, v in form.items())
    body += f"&token{_nanoid()}"
    r = await client.post(
        _SB_BASE_URL,
        content=body.encode(),
        headers=_SB_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


async def sb_search(
    client: httpx.AsyncClient,
    title: str,
    media_type: str,  # "movie" | "tv"
    page: int = 1,
    per_page: int = 20,
) -> list[dict]:
    """Search ShowBox — returns list of raw items."""
    sb_type = "movie" if media_type == "movie" else "tv"
    data = await _sb_request(
        client,
        "Search5",
        {"page": str(page), "type": sb_type, "keyword": title, "pagelimit": str(per_page)},
    )
    return data.get("data", {}).get("list") or []


async def sb_get_share_key(
    client: httpx.AsyncClient, item_id: int | str, box_type: int | str
) -> str | None:
    """Fetch the FebBox share key for a ShowBox item."""
    try:
        r = await client.get(
            f"https://www.showbox.media/index/share_link",
            params={"id": str(item_id), "type": str(box_type)},
            timeout=15,
            headers={"User-Agent": _FB_HEADERS["user-agent"]},
        )
        r.raise_for_status()
        data = r.json()
        link: str = data.get("data", {}).get("link", "") or ""
        # link = "https://www.febbox.com/share/XXXX"
        key = link.rstrip("/").split("/")[-1]
        return key if key else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# FebBox API
# ─────────────────────────────────────────────────────────────────────────────

def _fb_headers(share_key: str, ui_cookie: str) -> dict[str, str]:
    h = dict(_FB_HEADERS)
    h["referer"] = f"{_FB_BASE}/share/{share_key}"
    if ui_cookie:
        h["cookie"] = f"ui={ui_cookie}"
    return h


async def fb_file_list(
    client: httpx.AsyncClient,
    share_key: str,
    ui_cookie: str,
    parent_id: int = 0,
) -> list[dict]:
    """Get file list for a FebBox share."""
    url = (
        f"{_FB_BASE}/file/file_share_list"
        f"?share_key={share_key}&pwd=&parent_id={parent_id}&is_html=0"
    )
    r = await client.get(
        url,
        headers=_fb_headers(share_key, ui_cookie),
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("data", {}).get("file_list") or []


async def fb_video_qualities(
    client: httpx.AsyncClient,
    share_key: str,
    fid: int | str,
    ui_cookie: str,
) -> list[dict]:
    """
    Get quality list for a single file (parses HTML response).
    Returns list of {url, quality, name, size}.
    """
    url = f"{_FB_BASE}/console/video_quality_list?fid={fid}"
    r = await client.get(
        url,
        headers=_fb_headers(share_key, ui_cookie),
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    html = data.get("html", "")
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    results = []
    for div in soup.select(".file_quality"):
        stream_url = div.get("data-url", "")
        quality = div.get("data-quality", "")
        name_el = div.select_one(".name")
        size_el = div.select_one(".size")
        name = name_el.get_text(strip=True) if name_el else ""
        size = size_el.get_text(strip=True) if size_el else ""
        if stream_url:
            results.append(
                {
                    "url": stream_url,
                    "quality": quality,   # e.g. "4K", "1080P", "720P"
                    "name": name,
                    "size": size,
                }
            )
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Quality helpers
# ─────────────────────────────────────────────────────────────────────────────

def _quality_to_resolution(quality: str) -> int:
    """Convert FebBox quality label to integer resolution."""
    q = quality.strip().upper()
    if q in ("4K", "2160", "2160P", "UHD"):
        return 2160
    if q in ("1080P", "1080", "FHD"):
        return 1080
    if q in ("720P", "720", "HD"):
        return 720
    if q in ("480P", "480", "SD"):
        return 480
    if q in ("360P", "360"):
        return 360
    m = re.search(r"(\d{3,4})", q)
    if m:
        return int(m.group(1))
    return 0


def _parse_size_mb(size_str: str) -> float:
    """Parse size string like '2.3 GB' or '850 MB' into MB float."""
    if not size_str:
        return 0.0
    s = size_str.strip().upper()
    m = re.search(r"([\d.]+)\s*(GB|MB|KB)?", s)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2) or "MB"
    if unit == "GB":
        return val * 1024
    if unit == "KB":
        return val / 1024
    return val


# ─────────────────────────────────────────────────────────────────────────────
# High-level: search + resolve streams for a given title
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FebBoxStream:
    url: str
    resolution: int      # e.g. 2160, 1080, 720
    size_mb: float       # MB
    quality_label: str   # raw label from FebBox e.g. "4K", "1080P"
    filename: str        # e.g. "Avatar.2009.4K.mp4"


async def get_febbox_streams(
    title: str,
    year: str,
    media_type: str,         # "movie" | "series"
    ui_cookie: str,
    season: int = 1,
    episode: int = 1,
) -> list[FebBoxStream]:
    """
    Full pipeline: ShowBox search → share key → FebBox files → quality links.
    Returns list of FebBoxStream sorted by resolution desc.
    """
    if not ui_cookie:
        return []

    is_movie = media_type == "movie"
    sb_type = "movie" if is_movie else "tv"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 1. Search ShowBox
        try:
            items = await sb_search(client, title, sb_type, per_page=10)
        except Exception:
            return []

        if not items:
            return []

        # 2. Find matching item (by year if available)
        matched = None
        for item in items:
            if year:
                release = str(item.get("year", "") or item.get("released", "") or "")
                if year not in release:
                    continue
            matched = item
            break

        if not matched:
            # Relax year filter — take first result
            matched = items[0]

        item_id = matched.get("id") or matched.get("mid")
        box_type = matched.get("box_type", 1 if is_movie else 2)

        if not item_id:
            return []

        # 3. Get FebBox share key
        share_key = await sb_get_share_key(client, item_id, box_type)
        if not share_key:
            return []

        # 4. Get file list from FebBox
        try:
            files = await fb_file_list(client, share_key, ui_cookie)
        except Exception:
            return []

        if not files:
            return []

        # 5. For series: navigate to season/episode subfolder
        if not is_movie:
            files = await _resolve_series_files(
                client, share_key, ui_cookie, files, season, episode
            )

        if not files:
            return []

        # 6. For each video file, fetch quality links
        streams: list[FebBoxStream] = []
        for f in files:
            fid = f.get("fid")
            fname = f.get("file_name", "")
            if not fid:
                continue
            # Only process video files
            ftype = str(f.get("file_type", "")).lower()
            if ftype not in ("video", "") and not any(
                fname.lower().endswith(ext)
                for ext in (".mp4", ".mkv", ".avi", ".mov", ".webm")
            ):
                continue
            try:
                qualities = await fb_video_qualities(client, share_key, fid, ui_cookie)
            except Exception:
                continue
            for q in qualities:
                res = _quality_to_resolution(q["quality"])
                size_mb = _parse_size_mb(q.get("size", ""))
                streams.append(
                    FebBoxStream(
                        url=q["url"],
                        resolution=res,
                        size_mb=size_mb,
                        quality_label=q["quality"],
                        filename=fname,
                    )
                )

    # Sort by resolution desc
    streams.sort(key=lambda s: s.resolution, reverse=True)
    return streams


async def _resolve_series_files(
    client: httpx.AsyncClient,
    share_key: str,
    ui_cookie: str,
    root_files: list[dict],
    season: int,
    episode: int,
) -> list[dict]:
    """
    Navigate season/episode folders in FebBox.
    Tries to find Season N folder, then episode files within it.
    """
    # Look for a season folder (type=dir or is_dir)
    season_folder = None
    for f in root_files:
        if _is_folder(f):
            name = f.get("file_name", "").lower()
            if f"season {season}" in name or f"s{season:02d}" in name or f"s{season}" in name:
                season_folder = f
                break

    # If no season folder found, search directly in root files
    if not season_folder:
        return _filter_episode_files(root_files, episode)

    # Get files inside season folder
    parent_id = season_folder.get("fid", 0)
    try:
        season_files = await fb_file_list(client, share_key, ui_cookie, parent_id=parent_id)
    except Exception:
        return []

    return _filter_episode_files(season_files, episode)


def _is_folder(f: dict) -> bool:
    return (
        f.get("is_dir") == 1
        or str(f.get("file_type", "")).lower() == "dir"
        or f.get("file_type") == 0
    )


def _filter_episode_files(files: list[dict], episode: int) -> list[dict]:
    """Return files that match episode number."""
    ep_patterns = [
        re.compile(rf"[Ee]{episode:02d}"),
        re.compile(rf"[Ee]pisode\s*0*{episode}\b", re.IGNORECASE),
        re.compile(rf"\b0*{episode}\b"),
    ]
    matched = []
    for f in files:
        if _is_folder(f):
            continue
        name = f.get("file_name", "")
        for pat in ep_patterns:
            if pat.search(name):
                matched.append(f)
                break
    return matched if matched else [f for f in files if not _is_folder(f)]
