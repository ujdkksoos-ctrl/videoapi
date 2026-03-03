from fastapi import FastAPI, HTTPException
import yt_dlp
import uvicorn
import requests

app = FastAPI()

@app.get("/get_video")
async def get_video_info(url: str):
    ydl_opts_info = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = info.get('formats', [])
            duration = info.get('duration') 
            available_formats = []

            for f in formats:
                if f.get('ext') in ['mhtml'] or f.get('vcodec') == 'mhtml':
                    continue

                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                direct_url = f.get('url')

                # Identify if format has video, audio, or both
                has_video = vcodec != 'none'
                has_audio = acodec != 'none'

                # Define clear format type
                if has_video and has_audio:
                    format_type = "Video + Audio"
                elif has_video and not has_audio:
                    format_type = "Video Only (No Sound)"
                elif not has_video and has_audio:
                    format_type = "Audio Only"
                else:
                    format_type = "Unknown Type"

                # Resolution
                if not has_video and has_audio:
                    res = "Audio Only"
                else:
                    width = f.get('width', '?')
                    height = f.get('height', '?')
                    res = f"{width}x{height}" if width != '?' else f.get('resolution', 'Unknown')
                
                fps = f.get('fps')
                fps_str = f"{fps}fps" if fps else "N/A"
                quality_note = f.get('format_note', 'N/A')
                
                # Size calculation logic
                raw_size = f.get('filesize') or f.get('filesize_approx')

                if not raw_size and duration:
                    tbr = f.get('tbr')
                    if tbr:
                        raw_size = (tbr * 1000 * duration) / 8

                if not raw_size and direct_url:
                    try:
                        headers = {'User-Agent': ydl_opts_info['user_agent']}
                        head_req = requests.head(direct_url, headers=headers, allow_redirects=True, timeout=2)
                        if 'Content-Length' in head_req.headers:
                            raw_size = int(head_req.headers['Content-Length'])
                    except Exception:
                        pass 

                size_str = f"{float(raw_size)/(1024*1024):.2f} MB" if raw_size and raw_size > 0 else "Unknown"

                # Append to list
                available_formats.append({
                    "format_id": f.get('format_id', 'N/A'),
                    "format_type": format_type,      # Added: Clear type text
                    "has_video": has_video,          # Added: Boolean for video
                    "has_audio": has_audio,          # Added: Boolean for audio
                    "resolution": res,
                    "quality_note": quality_note,
                    "fps": fps_str,
                    "extension": f.get('ext', 'N/A'),
                    "size": size_str,
                    "vcodec": vcodec,
                    "acodec": acodec,
                    "direct_url": direct_url
                })

            available_formats.reverse()

            for index, item in enumerate(available_formats):
                item["sl"] = index + 1

            return {
                "status": "success",
                "platform": info.get('extractor_key', 'Unknown'),
                "title": info.get('title', 'Unknown Title'),
                "total_formats": len(available_formats),
                "formats_list": available_formats
            }
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8080)
