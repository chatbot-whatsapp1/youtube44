from fastapi import FastAPI, Query
import requests
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lê a chave do ambiente do Render
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def get_channel_id_from_handle(handle: str):
    handle = handle.replace("@", "")
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q={handle}&key={YOUTUBE_API_KEY}"
    data = requests.get(url).json()
    if "items" in data and len(data["items"]) > 0:
        return data["items"][0]["snippet"]["channelId"]
    return None

def extract_channel_id(channel_url: str):
    if "channel/" in channel_url:
        return channel_url.split("channel/")[1]
    elif "user/" in channel_url:
        username = channel_url.split("user/")[1]
        url = f"https://www.googleapis.com/youtube/v3/channels?forUsername={username}&part=id&key={YOUTUBE_API_KEY}"
        data = requests.get(url).json()
        return data["items"][0]["id"] if "items" in data else None
    elif "@" in channel_url:
        handle = channel_url.split("@")[1].split("/")[0]
        return get_channel_id_from_handle(handle)
    return None


@app.get("/api/channel_stats")
def get_channel_stats(
    channel_url: str = Query(..., description="URL do canal do YouTube"),
    start_date: str = Query(None, description="Data inicial (YYYY-MM-DD)"),
    end_date: str = Query(None, description="Data final (YYYY-MM-DD)")
):
    channel_id = extract_channel_id(channel_url)
    if not channel_id:
        return {"error": "URL inválida"}

    videos = []
    url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={channel_id}&part=snippet,id&maxResults=50&order=date"
    response = requests.get(url).json()

    for item in response.get("items", []):
        if item["id"]["kind"] != "youtube#video":
            continue

        snippet = item["snippet"]
        published_at = snippet["publishedAt"][:10]  # Pega apenas a data YYYY-MM-DD

        # Se houver filtro de datas, aplica
        if start_date and published_at < start_date:
            continue
        if end_date and published_at > end_date:
            continue

        vid_id = item["id"]["videoId"]
        stats_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id={vid_id}&key={YOUTUBE_API_KEY}"
        stats_data = requests.get(stats_url).json()
        if "items" not in stats_data:
            continue

        video = stats_data["items"][0]
        stats = video["statistics"]
        videos.append({
            "canal": channel_url,
            "titulo": snippet["title"],
            "publicado_em": published_at,
            "views": stats.get("viewCount", "0"),
            "likes": stats.get("likeCount", "0"),
            "comentarios": stats.get("commentCount", "0"),
            "url": f"https://www.youtube.com/watch?v={vid_id}"
        })

    return {"canal_id": channel_id, "videos": videos}
