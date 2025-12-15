from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pytubefix import YouTube, Playlist
from pytubefix.exceptions import AgeRestrictedError, VideoUnavailable, RegexMatchError
import os
import tempfile
import shutil
import re

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DOWNLOAD_FOLDER = tempfile.gettempdir()

def sanitize_filename(filename):
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = filename.strip()
    if len(filename) > 200:
        filename = filename[:200]
    return filename

def format_duration(seconds):
    if not seconds:
        return None
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

@app.route('/')
def home():
    return jsonify({
        'message': 'YouTube Downloader API - PyTube Edition',
        'version': '2.0',
        'endpoints': {
            '/info': 'GET - Obter informações completas do vídeo',
            '/download': 'GET - Baixar vídeo (params: url, quality)',
            '/download-audio': 'GET - Baixar apenas áudio MP3/MP4',
            '/formats': 'GET - Listar todos os formatos disponíveis',
            '/thumbnail': 'GET - Obter URL da thumbnail em alta qualidade',
            '/playlist': 'GET - Obter informações de uma playlist',
        },
        'quality_options': ['highest', 'lowest', '1080p', '720p', '480p', '360p', '240p', '144p'],
        'supported_sites': 'YouTube apenas',
        'library': 'pytube'
    })

@app.route('/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        yt = YouTube(url)

        return jsonify({
            'title': yt.title,
            'description': yt.description[:500] if yt.description else None,
            'duration': yt.length,
            'duration_string': format_duration(yt.length),
            'thumbnail': yt.thumbnail_url,
            'uploader': yt.author,
            'channel_id': yt.channel_id,
            'channel_url': yt.channel_url,
            'view_count': yt.views,
            'publish_date': yt.publish_date.isoformat() if yt.publish_date else None,
            'rating': yt.rating,
            'age_restricted': yt.age_restricted,
            'video_id': yt.video_id,
            'webpage_url': yt.watch_url,
            'keywords': yt.keywords[:10] if yt.keywords else [],
            'format_count': len(yt.streams),
        })

    except AgeRestrictedError:
        return jsonify({'error': 'Vídeo com restrição de idade'}), 403
    except VideoUnavailable:
        return jsonify({'error': 'Vídeo indisponível ou privado'}), 404
    except RegexMatchError:
        return jsonify({'error': 'URL inválida'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/formats', methods=['GET'])
def list_formats():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        yt = YouTube(url)
        formats = []

        for stream in yt.streams:
            format_info = {
                'itag': stream.itag,
                'mime_type': stream.mime_type,
                'resolution': stream.resolution,
                'fps': stream.fps,
                'video_codec': stream.video_codec,
                'audio_codec': stream.audio_codec,
                'is_progressive': stream.is_progressive,
                'is_adaptive': stream.is_adaptive,
                'includes_video': stream.includes_video_track,
                'includes_audio': stream.includes_audio_track,
                'filesize': stream.filesize,
                'filesize_mb': round(stream.filesize / (1024 * 1024), 2) if stream.filesize else None,
                'abr': stream.abr,
                'type': stream.type,
            }
            formats.append(format_info)

        return jsonify({
            'title': yt.title,
            'formats': formats,
            'format_count': len(formats),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['GET'])
def download_video():
    url = request.args.get('url')
    quality = request.args.get('quality', 'highest')

    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        yt = YouTube(url)
        download_path = os.path.join(DOWNLOAD_FOLDER, 'yt_downloads')
        os.makedirs(download_path, exist_ok=True)

        # Selecionar stream baseado na qualidade
        if quality == 'highest':
            stream = yt.streams.get_highest_resolution()
        elif quality == 'lowest':
            stream = yt.streams.get_lowest_resolution()
        else:
            # Tentar resolução específica (1080p, 720p, etc)
            stream = yt.streams.filter(res=quality, progressive=True).first()
            if not stream:
                # Se não encontrar progressivo, pegar adaptativo
                stream = yt.streams.filter(res=quality).first()
            if not stream:
                # Fallback para melhor qualidade
                stream = yt.streams.get_highest_resolution()

        if not stream:
            return jsonify({'error': 'Nenhum formato disponível'}), 404

        # Baixar o vídeo
        filename = stream.download(output_path=download_path)

        if not os.path.exists(filename):
            return jsonify({'error': 'Erro ao baixar o arquivo'}), 500

        response = send_file(
            filename,
            as_attachment=True,
            download_name=sanitize_filename(os.path.basename(filename))
        )

        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(filename):
                    os.remove(filename)
                if os.path.exists(download_path) and not os.listdir(download_path):
                    shutil.rmtree(download_path)
            except:
                pass

        return response

    except AgeRestrictedError:
        return jsonify({'error': 'Vídeo com restrição de idade'}), 403
    except VideoUnavailable:
        return jsonify({'error': 'Vídeo indisponível'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download-audio', methods=['GET'])
def download_audio():
    url = request.args.get('url')

    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        yt = YouTube(url)
        download_path = os.path.join(DOWNLOAD_FOLDER, 'yt_downloads')
        os.makedirs(download_path, exist_ok=True)

        # Pegar melhor stream de áudio
        stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()

        if not stream:
            return jsonify({'error': 'Nenhum áudio disponível'}), 404

        # Baixar o áudio
        filename = stream.download(output_path=download_path)

        if not os.path.exists(filename):
            return jsonify({'error': 'Erro ao baixar o áudio'}), 500

        # Renomear para indicar que é áudio
        title = sanitize_filename(yt.title)
        audio_filename = os.path.join(download_path, f"{title}_audio.mp4")

        if os.path.exists(audio_filename):
            os.remove(audio_filename)
        os.rename(filename, audio_filename)

        response = send_file(
            audio_filename,
            as_attachment=True,
            download_name=f"{title}_audio.mp4"
        )

        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(audio_filename):
                    os.remove(audio_filename)
                if os.path.exists(download_path) and not os.listdir(download_path):
                    shutil.rmtree(download_path)
            except:
                pass

        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/thumbnail', methods=['GET'])
def get_thumbnail():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        yt = YouTube(url)

        # PyTube retorna apenas uma thumbnail, mas podemos construir outras URLs
        video_id = yt.video_id
        thumbnails = [
            {
                'quality': 'maxresdefault',
                'url': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
                'width': 1280,
                'height': 720
            },
            {
                'quality': 'sddefault',
                'url': f'https://img.youtube.com/vi/{video_id}/sddefault.jpg',
                'width': 640,
                'height': 480
            },
            {
                'quality': 'hqdefault',
                'url': f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg',
                'width': 480,
                'height': 360
            },
            {
                'quality': 'mqdefault',
                'url': f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg',
                'width': 320,
                'height': 180
            },
            {
                'quality': 'default',
                'url': f'https://img.youtube.com/vi/{video_id}/default.jpg',
                'width': 120,
                'height': 90
            }
        ]

        return jsonify({
            'title': yt.title,
            'thumbnails': thumbnails,
            'best': thumbnails[0]['url'],
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/playlist', methods=['GET'])
def get_playlist_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        pl = Playlist(url)

        videos = []
        for video_url in pl.video_urls[:50]:  # Limitar a 50 vídeos
            try:
                yt = YouTube(video_url)
                videos.append({
                    'id': yt.video_id,
                    'title': yt.title,
                    'url': yt.watch_url,
                    'duration': yt.length,
                    'thumbnail': yt.thumbnail_url,
                    'author': yt.author,
                })
            except:
                continue

        return jsonify({
            'title': pl.title,
            'owner': pl.owner if hasattr(pl, 'owner') else None,
            'video_count': len(pl.video_urls),
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