from flask import Flask, request, send_file, jsonify, Response
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import shutil
import re

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DOWNLOAD_FOLDER = tempfile.gettempdir()

BASE_YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': False,
    'no_color': True,
    'noprogress': True,
    'geo_bypass': True,
    'geo_bypass_country': 'US',
    'socket_timeout': 30,
    'retries': 10,
    'fragment_retries': 10,
    'skip_unavailable_fragments': True,
    'keepvideo': False,
    'overwrites': True,
    'noplaylist': True,
    'extract_flat': False,
    'age_limit': None,
    'source_address': '0.0.0.0',
    'force_ipv4': True,
    'prefer_insecure': False,
    'legacyserverconnect': False,
    'nocheckcertificate': False,
    'prefer_ffmpeg': True,
    'hls_prefer_native': False,
    'external_downloader_args': None,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web', 'ios', 'mweb'],
            'player_skip': ['webpage', 'configs'],
            'skip': ['hls', 'dash'],
        }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    },
    'compat_opts': set(),
}

FORMAT_OPTIONS = {
    'best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best',
    'best_video': 'bestvideo[ext=mp4]/bestvideo/best',
    'best_audio': 'bestaudio[ext=m4a]/bestaudio/best',
    'worst': 'worstvideo+worstaudio/worst',
    '1080p': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]',
    '720p': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]',
    '480p': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]',
    '360p': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]',
    'mp3': 'bestaudio/best',
    'mp4': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'webm': 'bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best',
}

def sanitize_filename(filename):
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = filename.strip()
    if len(filename) > 200:
        filename = filename[:200]
    return filename

def get_ydl_opts(**kwargs):
    opts = BASE_YDL_OPTS.copy()
    opts.update(kwargs)
    return opts

@app.route('/')
def home():
    return jsonify({
        'message': 'YouTube Downloader API - Completa',
        'version': '2.0',
        'endpoints': {
            '/info': 'GET - Obter informações completas do vídeo',
            '/download': 'GET - Baixar vídeo (params: url, format, quality)',
            '/download-audio': 'GET - Baixar apenas áudio MP3',
            '/formats': 'GET - Listar todos os formatos disponíveis',
            '/get-link': 'GET - Obter link direto do vídeo',
            '/thumbnail': 'GET - Obter URL da thumbnail em alta qualidade',
            '/subtitles': 'GET - Listar legendas disponíveis',
            '/playlist': 'GET - Obter informações de uma playlist',
        },
        'format_options': list(FORMAT_OPTIONS.keys()),
        'supported_sites': 'YouTube, Vimeo, Dailymotion, Facebook, Twitter, Instagram, TikTok, e 1000+ outros'
    })

@app.route('/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        ydl_opts = get_ydl_opts()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            thumbnails = info.get('thumbnails', [])
            best_thumbnail = thumbnails[-1]['url'] if thumbnails else info.get('thumbnail')
            
            categories = info.get('categories', [])
            tags = info.get('tags', [])
            
            return jsonify({
                'title': info.get('title'),
                'description': info.get('description', '')[:500] if info.get('description') else None,
                'duration': info.get('duration'),
                'duration_string': info.get('duration_string'),
                'thumbnail': best_thumbnail,
                'thumbnails': [t.get('url') for t in thumbnails[-5:]] if thumbnails else [],
                'uploader': info.get('uploader'),
                'uploader_id': info.get('uploader_id'),
                'uploader_url': info.get('uploader_url'),
                'channel': info.get('channel'),
                'channel_id': info.get('channel_id'),
                'channel_url': info.get('channel_url'),
                'view_count': info.get('view_count'),
                'like_count': info.get('like_count'),
                'comment_count': info.get('comment_count'),
                'upload_date': info.get('upload_date'),
                'release_date': info.get('release_date'),
                'age_limit': info.get('age_limit'),
                'categories': categories[:5] if categories else [],
                'tags': tags[:10] if tags else [],
                'is_live': info.get('is_live', False),
                'was_live': info.get('was_live', False),
                'availability': info.get('availability'),
                'webpage_url': info.get('webpage_url'),
                'original_url': info.get('original_url'),
                'extractor': info.get('extractor'),
                'format_count': len(info.get('formats', [])),
            })

    except yt_dlp.utils.DownloadError as e:
        return jsonify({'error': f'Erro de download: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/formats', methods=['GET'])
def list_formats():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        ydl_opts = get_ydl_opts()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            
            for f in info.get('formats', []):
                format_info = {
                    'format_id': f.get('format_id'),
                    'format_note': f.get('format_note'),
                    'ext': f.get('ext'),
                    'resolution': f.get('resolution'),
                    'width': f.get('width'),
                    'height': f.get('height'),
                    'fps': f.get('fps'),
                    'filesize': f.get('filesize'),
                    'filesize_approx': f.get('filesize_approx'),
                    'tbr': f.get('tbr'),
                    'vbr': f.get('vbr'),
                    'abr': f.get('abr'),
                    'asr': f.get('asr'),
                    'vcodec': f.get('vcodec'),
                    'acodec': f.get('acodec'),
                    'has_video': f.get('vcodec') != 'none',
                    'has_audio': f.get('acodec') != 'none',
                    'quality': f.get('quality'),
                    'dynamic_range': f.get('dynamic_range'),
                    'audio_channels': f.get('audio_channels'),
                }
                formats.append(format_info)
            
            return jsonify({
                'title': info.get('title'),
                'formats': formats,
                'format_count': len(formats),
                'recommended_formats': list(FORMAT_OPTIONS.keys()),
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['GET'])
def download_video():
    url = request.args.get('url')
    quality = request.args.get('quality', 'best')
    format_type = request.args.get('format', 'mp4')

    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        download_path = os.path.join(DOWNLOAD_FOLDER, 'yt_downloads')
        os.makedirs(download_path, exist_ok=True)

        format_string = FORMAT_OPTIONS.get(quality, FORMAT_OPTIONS['best'])
        
        ydl_opts = get_ydl_opts(
            format=format_string,
            outtmpl=os.path.join(download_path, '%(title)s.%(ext)s'),
            merge_output_format=format_type if format_type in ['mp4', 'mkv', 'webm'] else 'mp4',
            postprocessors=[{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': format_type if format_type in ['mp4', 'mkv', 'webm', 'avi', 'mov'] else 'mp4',
            }] if format_type not in ['mp4', 'webm'] else [],
            writesubtitles=False,
            writeautomaticsub=False,
            embedsubtitles=False,
            writethumbnail=False,
            embedthumbnail=False,
            addmetadata=True,
            embedmetadata=True,
        )

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            base, ext = os.path.splitext(filename)
            possible_extensions = [ext, '.mp4', '.webm', '.mkv', '.avi', '.mov']
            actual_file = None
            
            for possible_ext in possible_extensions:
                test_path = base + possible_ext
                if os.path.exists(test_path):
                    actual_file = test_path
                    break
            
            if not actual_file:
                for f in os.listdir(download_path):
                    if info.get('title', '')[:50] in f:
                        actual_file = os.path.join(download_path, f)
                        break

            if not actual_file or not os.path.exists(actual_file):
                return jsonify({'error': 'Erro ao localizar o arquivo baixado'}), 500

            response = send_file(
                actual_file,
                as_attachment=True,
                download_name=sanitize_filename(os.path.basename(actual_file))
            )

            @response.call_on_close
            def cleanup():
                try:
                    if os.path.exists(actual_file):
                        os.remove(actual_file)
                    if os.path.exists(download_path) and not os.listdir(download_path):
                        shutil.rmtree(download_path)
                except:
                    pass

            return response

    except yt_dlp.utils.DownloadError as e:
        return jsonify({'error': f'Erro de download: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download-audio', methods=['GET'])
def download_audio():
    url = request.args.get('url')
    audio_format = request.args.get('format', 'mp3')
    quality = request.args.get('quality', '192')

    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        download_path = os.path.join(DOWNLOAD_FOLDER, 'yt_downloads')
        os.makedirs(download_path, exist_ok=True)

        ydl_opts = get_ydl_opts(
            format='bestaudio/best',
            outtmpl=os.path.join(download_path, '%(title)s.%(ext)s'),
            postprocessors=[{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_format,
                'preferredquality': quality,
            }],
            prefer_ffmpeg=True,
            keepvideo=False,
        )

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = sanitize_filename(info.get('title', 'audio'))
            
            audio_file = None
            for f in os.listdir(download_path):
                if f.endswith(f'.{audio_format}'):
                    audio_file = os.path.join(download_path, f)
                    break

            if not audio_file or not os.path.exists(audio_file):
                return jsonify({'error': 'Erro ao processar áudio'}), 500

            response = send_file(
                audio_file,
                as_attachment=True,
                download_name=f"{title}.{audio_format}"
            )

            @response.call_on_close
            def cleanup():
                try:
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                    if os.path.exists(download_path) and not os.listdir(download_path):
                        shutil.rmtree(download_path)
                except:
                    pass

            return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-link', methods=['GET'])
def get_download_link():
    url = request.args.get('url')
    quality = request.args.get('quality', 'best')

    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        ydl_opts = get_ydl_opts()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            video_audio_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
            video_only = [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') == 'none']
            audio_only = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
            
            best_combined = video_audio_formats[-1] if video_audio_formats else None
            best_video = video_only[-1] if video_only else None
            best_audio = audio_only[-1] if audio_only else None

            return jsonify({
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'best_combined': {
                    'url': best_combined.get('url'),
                    'ext': best_combined.get('ext'),
                    'resolution': best_combined.get('resolution'),
                    'filesize': best_combined.get('filesize'),
                } if best_combined else None,
                'best_video': {
                    'url': best_video.get('url'),
                    'ext': best_video.get('ext'),
                    'resolution': best_video.get('resolution'),
                    'filesize': best_video.get('filesize'),
                } if best_video else None,
                'best_audio': {
                    'url': best_audio.get('url'),
                    'ext': best_audio.get('ext'),
                    'abr': best_audio.get('abr'),
                    'filesize': best_audio.get('filesize'),
                } if best_audio else None,
                'direct_url': info.get('url'),
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/thumbnail', methods=['GET'])
def get_thumbnail():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        ydl_opts = get_ydl_opts()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            thumbnails = info.get('thumbnails', [])
            
            sorted_thumbs = sorted(
                [t for t in thumbnails if t.get('width')],
                key=lambda x: x.get('width', 0),
                reverse=True
            )
            
            return jsonify({
                'title': info.get('title'),
                'thumbnails': [
                    {
                        'url': t.get('url'),
                        'width': t.get('width'),
                        'height': t.get('height'),
                        'resolution': t.get('resolution'),
                    } for t in sorted_thumbs[:10]
                ],
                'best': sorted_thumbs[0].get('url') if sorted_thumbs else info.get('thumbnail'),
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/subtitles', methods=['GET'])
def get_subtitles():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        ydl_opts = get_ydl_opts(writesubtitles=True, allsubtitles=True)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            subtitles = info.get('subtitles', {})
            auto_captions = info.get('automatic_captions', {})
            
            return jsonify({
                'title': info.get('title'),
                'subtitles': list(subtitles.keys()),
                'automatic_captions': list(auto_captions.keys()),
                'has_subtitles': len(subtitles) > 0,
                'has_auto_captions': len(auto_captions) > 0,
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/playlist', methods=['GET'])
def get_playlist_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        ydl_opts = get_ydl_opts(extract_flat='in_playlist', noplaylist=False)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            entries = info.get('entries', [])
            videos = []
            for entry in entries[:50]:
                if entry:
                    videos.append({
                        'id': entry.get('id'),
                        'title': entry.get('title'),
                        'url': entry.get('url') or entry.get('webpage_url'),
                        'duration': entry.get('duration'),
                        'thumbnail': entry.get('thumbnail'),
                    })
            
            return jsonify({
                'title': info.get('title'),
                'uploader': info.get('uploader'),
                'description': info.get('description', '')[:500] if info.get('description') else None,
                'video_count': len(entries),
                'videos': videos,
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint não encontrado'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Erro interno do servidor'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
