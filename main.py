from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import requests
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def iso_date(date_str: str) -> str:
    # espera YYYY-MM-DD; retorna o mesmo se válido, senão None
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except:
        return None

def get_channel_id_from_handle(handle: str):
    handle = handle.strip().replace("@", "")
    # Busca canal pelo handle usando a Search API (type=channel)
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q={handle}&key={YOUTUBE_API_KEY}&maxResults=1"
    data = requests.get(url, timeout=20).json()
    if "items" in data and data["items"]:
        return data["items"][0]["snippet"]["channelId"]
    return None

def extract_channel_id(channel_url: str):
    channel_url = (channel_url or "").strip()
    if not channel_url:
        return None
    if "channel/" in channel_url:
        return channel_url.split("channel/")[1].split("/")[0]
    if "user/" in channel_url:
        username = channel_url.split("user/")[1].split("/")[0]
        url = f"https://www.googleapis.com/youtube/v3/channels?forUsername={username}&part=id&key={YOUTUBE_API_KEY}"
        data = requests.get(url, timeout=20).json()
        return data["items"][0]["id"] if "items" in data and data["items"] else None
    if "@" in channel_url:
        handle = channel_url.split("@")[1].split("/")[0]
        return get_channel_id_from_handle(handle)
    # caso a pessoa cole só o handle, sem https
    if channel_url.startswith("@"):
        return get_channel_id_from_handle(channel_url[1:])
    return None

def fetch_channel_rows(channel_url: str, start_date: str, end_date: str, limit: int):
    """
    Retorna uma LISTA de linhas 'achatadas':
    {
      "channel": "<url ou handle informado>",
      "title": "...",
      "views": 123,
      "likes": 10,
      "published": "YYYY-MM-DD",
      "video_url": "..."
    }
    """
    rows = []
    channel_id = extract_channel_id(channel_url)
    if not channel_id:
        return rows  # vazio, deixa o chamador decidir

    # Busca últimos vídeos (ordenados por data desc)
    search_url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?key={YOUTUBE_API_KEY}&channelId={channel_id}&part=snippet,id"
        f"&maxResults=50&order=date"
    )
    data = requests.get(search_url, timeout=30).json()
    items = data.get("items", [])

    # filtro de datas (YYYY-MM-DD)
    sdate = iso_date(start_date) if start_date else None
    edate = iso_date(end_date) if end_date else None

    for item in items:
        if item.get("id", {}).get("kind") != "youtube#video":
            continue
        snippet = item.get("snippet", {})
        published_at = snippet.get("publishedAt", "")[:10]

        if sdate and published_at < sdate:
            continue
        if edate and published_at > edate:
            continue

        vid_id = item["id"]["videoId"]
        stats_url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=statistics,snippet&id={vid_id}&key={YOUTUBE_API_KEY}"
        )
        vdata = requests.get(stats_url, timeout=20).json()
        if "items" not in vdata or not vdata["items"]:
            continue
        v = vdata["items"][0]
        stats = v.get("statistics", {})
        title = v.get("snippet", {}).get("title", "")

        row = {
            "channel": channel_url,
            "title": title,
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "published": published_at,
            "video_url": f"https://www.youtube.com/watch?v={vid_id}"
        }
        rows.append(row)

        if len(rows) >= max(1, min(limit or 20, 100)):  # segurança: 1..100
            break

    return rows


@app.get("/api/channel_stats_table")
def channel_stats_table(
    channel_url: str = Query(..., description="URL ou @handle do canal"),
    start_date: str = Query(None, description="YYYY-MM-DD"),
    end_date: str = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(20, description="Máximo de linhas retornadas (1..100)")
):
    # Retorna DIRETAMENTE uma lista de linhas (ideal pro Base44 / tabela)
    rows = fetch_channel_rows(channel_url, start_date, end_date, limit)
    return rows


@app.get("/api/multi_channel_stats_table")
def multi_channel_stats_table(
    channels: str = Query(..., description="Lista de canais separada por vírgula ou quebra de linha"),
    start_date: str = Query(None, description="YYYY-MM-DD"),
    end_date: str = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(10, description="Máx. de vídeos por canal (1..50)")
):
    """
    'channels' pode ser:
      - "https://youtube.com/@canal1, https://youtube.com/@canal2"
      - "@canal1\n@canal2\nhttps://youtube.com/channel/..."
    Retorna UMA lista única com linhas de todos os canais.
    """
    # normaliza separadores (vírgula e quebras de linha)
    raw = channels.replace("\r", "\n")
    parts = []
    for chunk in raw.split("\n"):
        parts += [p.strip() for p in chunk.split(",") if p.strip()]
    parts = [p for p in parts if p]  # remove vazios

    merged = []
    for ch in parts[:10]:  # segurança: no máx. 10 canais por chamada
        merged += fetch_channel_rows(ch, start_date, end_date, limit)

    # Ordena por data desc só pra ficar agradável
    merged.sort(key=lambda r: r.get("published", ""), reverse=True)
    return merged
