# Stremio MovieBox Addon

A high-performance Stremio addon that bridges MovieBox's vast streaming catalog directly to your Stremio experience. It automatically searches across multiple internal MovieBox APIs (Legacy, Web, and Mobile) to provide the highest quality streams, complete with audio dub and subtitle information.

## Features

- **Multi-API Scraping:** Concurrently queries MovieBox's v1, v2, and v3 APIs to ensure maximum stream availability.
- **Deduplication:** Intelligently merges identical streams and groups them by resolution and audio language.
- **Stremio Native:** Fully compatible with Stremio's addon system, including Cinemeta integration and robust metadata matching.
- **Fast & Asynchronous:** Built with FastAPI and httpx for highly concurrent, non-blocking requests.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended for dependency management) or pip.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mesamirh/stremio-moviebox.git
   cd stremio-moviebox
   ```

2. **Install dependencies:**
   Using `uv`:
   ```bash
   uv sync
   ```
   Or using pip:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy the example environment file and update it with your settings (including proxy details if needed):
   ```bash
   cp .env.example .env
   ```

## Usage

Start the local server using the Makefile:

```bash
make start
```

This will spin up a Uvicorn server on `http://127.0.0.1:8000`. 

To install the addon in Stremio, simply navigate to `http://127.0.0.1:8000/manifest.json` in your browser, or paste that link directly into the Stremio Addons search bar.

## Architecture

- `server/`: Contains the FastAPI application, routes, and Stremio manifest generation.
- `streaming/`: Contains the core logic for translating Stremio's Cinemeta requests into MovieBox API calls, stream deduplication, and title formatting.
- `moviebox/`: The reverse-engineered internal MovieBox API clients, supporting legacy (v1), web (v2), and mobile (v3) authentication and streaming extraction.

## Disclaimer

This addon is intended for educational purposes. It scrapes publicly available content from third-party APIs. The developers of this addon are not affiliated with MovieBox or Stremio.
