from fastapi import FastAPI
import requests
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

YOUTUBE_API_KEY = "SUA_API_KEY_AQUI"

def extract_channel_id(channel_url):
    if "channel/" in channel_url:
        return channel_url.split("channel/")[1]
    elif "user/" in channel_url:
        username = channel_url.split("user/")[1]
        url = f"https://www.googleapis.com/youtube/v3/channels?forUsername={username}&part=id&key={YOUTUBE_API_KEY}"
        data = requests.get(url).json()
        return data["items"][0]["id"] if "items" in data else None
    elif "@" in channel_url:
        handle = channel_url.split("@")[1].split("/")[0]
        url = f"https://www.googleapis.com/youtube/v3/channels?part=id&forUsername={handle}&key={YOUTUBE_API_KEY}"
        data = requests.get(url).json()
        return data["items"][0]["id"] if "items" in data else None
    return None

@app.get("/api/channel_stats")
def get_channel_stats(channel_url: str):
    channel_id = extract_channel_id(channel_url)
    if not channel_id:
        return {"error": "URL inválida"}

    videos = []
    url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={channel_id}&part=snippet,id&maxResults=20&order=date"
    response = requests.get(url).json()

    for item in response.get("items", []):
        if item["id"]["kind"] == "youtube#video":
            vid_id = item["id"]["videoId"]
            stats_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id={vid_id}&key={YOUTUBE_API_KEY}"
            stats_data = requests.get(stats_url).json()
            if "items" not in stats_data:
                continue
            video = stats_data["items"][0]
            snippet = video["snippet"]
            stats = video["statistics"]
            videos.append({
                "titulo": snippet["title"],
                "publicado_em": snippet["publishedAt"],
                "views": stats.get("viewCount", "0"),
                "likes": stats.get("likeCount", "0"),
                "comentarios": stats.get("commentCount", "0"),
                "url": f"https://www.youtube.com/watch?v={vid_id}"
            })
    return {"canal_id": channel_id, "videos": videos}
