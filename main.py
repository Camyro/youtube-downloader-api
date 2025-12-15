from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import shutil

app = Flask(__name__)
CORS(app)

# Criar pasta temporária para downloads
DOWNLOAD_FOLDER = tempfile.gettempdir()

@app.route('/')
def home():
    return jsonify({
        'message': 'YouTube Downloader API',
        'endpoints': {
            '/info': 'GET - Obter informações do vídeo',
            '/download': 'GET - Baixar vídeo',
            '/get-link': 'GET - Obter link direto'
        }
    })

@app.route('/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')

    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return jsonify({
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'uploader': info.get('uploader'),
                'view_count': info.get('view_count'),
                'upload_date': info.get('upload_date'),
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['GET'])
def download_video():
    url = request.args.get('url')

    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        # Criar pasta temporária única para este download
        download_path = os.path.join(DOWNLOAD_FOLDER, 'yt_downloads')
        os.makedirs(download_path, exist_ok=True)

        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            if not os.path.exists(filename):
                return jsonify({'error': 'Erro ao baixar o arquivo'}), 500

            response = send_file(
                filename,
                as_attachment=True,
                download_name=os.path.basename(filename)
            )

            # Agendar limpeza do arquivo após envio
            @response.call_on_close
            def cleanup():
                try:
                    if os.path.exists(filename):
                        os.remove(filename)
                    # Limpar pasta se estiver vazia
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
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': 'caminho/do/arquivo.mp4',
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['ios', 'web']}},
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Buscar melhor formato disponível
            formats = info.get('formats', [])
            best_format = None

            for fmt in reversed(formats):
                if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                    best_format = fmt
                    break

            if not best_format and formats:
                best_format = formats[-1]

            return jsonify({
                'title': info.get('title'),
                'url': best_format.get('url') if best_format else info.get('url'),
                'ext': info.get('ext'),
                'filesize': best_format.get('filesize') if best_format else None,
                'resolution': best_format.get('resolution') if best_format else None,
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Replit usa porta 5000 por padrão, mas é bom deixar flexível
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)