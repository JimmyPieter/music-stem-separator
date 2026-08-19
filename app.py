
import os
import sys
import threading
import time
import uuid
from pathlib import Path

import ffmpeg
from flask import Flask, render_template, request, jsonify, url_for, redirect, send_from_directory
from werkzeug.utils import secure_filename

from music_processor import MusicProcessor

from karaoke import KaraokeCreator

from smart_processor import SmartProcessor

from youtube_downloader import YouTubeAudioDownloader

from bs_roformer_separator import BSRoformerProcessor
from vocal_choir_separator import VocalChoirProcessor

# Set console encoding for Windows
if sys.platform == 'win32':
    import io
    # Only wrap if not already wrapped
    if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if not isinstance(sys.stderr, io.TextIOWrapper) or sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
UPLOAD_DIR = Path('uploads')
SUPPORTED_AUDIO_EXTENSIONS = {
    '.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.opus', '.wma'
}
VALID_ACTIONS = {
    'download', 'karaoke', '4-stem', '6-stem', 'bs-6-stem',
    'guitar-karaoke', 'vocal-choir'
}
OUTPUT_FORMATS = {'mp3', 'wav'}

# --- State Management ---
# A simple in-memory store for job status.
# For a real-world app, you'd use a database or a task queue like Celery.
job_status = {
    'is_running': False,
    'progress': 0,
    'percentage': 0,
    'total': 0,
    'current_task': 'Waiting to start...',
    'error': None,
    'output_files': []
}

# --- Background Processing ---
def run_processing_job(urls, uploaded_files, mode, model, output_format,
                       high_performance):
    """The actual processing function that runs in a background thread."""
    global job_status
    job_status['is_running'] = True
    job_status['progress'] = 0
    job_status['percentage'] = 0
    sources = [('url', url) for url in urls] + [
        ('file', str(UPLOAD_DIR / filename)) for filename in uploaded_files
    ]
    job_status['total'] = len(sources)
    job_status['error'] = None
    job_status['output_files'] = []

    processor = None
    if mode == 'karaoke':
        processor = KaraokeCreator(model=model, high_performance=high_performance)
    elif mode == 'vocal-choir':
        processor = VocalChoirProcessor(high_performance=high_performance)
    elif mode == 'download':
        processor = YouTubeAudioDownloader(
            output_dir='downloads', format=output_format
        )
    elif mode in ('bs-6-stem', 'guitar-karaoke'):
        processor = BSRoformerProcessor(
            output_dir='karaoke' if mode == 'guitar-karaoke' else 'separated'
        )
    else: # '4-stem' or '6-stem'
        processor = MusicProcessor(model=model, high_performance=high_performance)

    for i, (source_type, source) in enumerate(sources):
        label = Path(source).name if source_type == 'file' else source
        job_status['current_task'] = f"Processing {i+1}/{len(sources)}: {label}"
        job_status['percentage'] = round(i / len(sources) * 100)
        if mode in ('bs-6-stem', 'guitar-karaoke'):
            def update_bs_progress(item_percentage, message, item_index=i):
                job_status['percentage'] = round(
                    (item_index + item_percentage / 100) / len(sources) * 100
                )
                job_status['current_task'] = (
                    f"Item {item_index + 1}/{len(sources)}: {message}"
                )
            processor.separator.progress_callback = update_bs_progress
        elif mode == 'vocal-choir':
            def update_vocal_progress(item_percentage, message, item_index=i):
                job_status['percentage'] = round(
                    (item_index + item_percentage / 100) / len(sources) * 100
                )
                job_status['current_task'] = (
                    f"Item {item_index + 1}/{len(sources)}: {message}"
                )
            processor.progress_callback = update_vocal_progress
        try:
            if mode == 'karaoke':
                result = (processor.create_from_youtube(
                              source, keep_original=False,
                              output_format=output_format)
                          if source_type == 'url' else processor.create_from_file(
                              source, output_format=output_format))
                job_status['output_files'].extend(result.values())
            elif mode == 'vocal-choir':
                result = (processor.process_from_youtube(
                              source, output_format=output_format)
                          if source_type == 'url'
                          else processor.process_local_file(
                              source, output_format=output_format))
                job_status['output_files'].extend(result.values())
            elif mode == 'download':
                if source_type == 'url':
                    result_file = processor.download(source)
                elif Path(source).suffix.lower() == f'.{output_format}':
                    result_file = source
                else:
                    output_path = Path('downloads') / (
                        f'{Path(source).stem}.{output_format}'
                    )
                    ffmpeg.output(
                        ffmpeg.input(source).audio, str(output_path)
                    ).overwrite_output().run(quiet=True)
                    result_file = output_path.as_posix()
                job_status['output_files'].append(result_file)
            elif mode == 'guitar-karaoke':
                result = (processor.create_guitar_karaoke_from_youtube(
                              source, output_format=output_format)
                          if source_type == 'url'
                          else processor.create_guitar_karaoke_from_file(
                              source, output_format=output_format))
                job_status['output_files'].extend(result.values())
            else:
                if source_type == 'url':
                    _, stems = processor.process_from_youtube(
                        url=source, keep_original=False,
                        output_format=output_format
                    )
                else:
                    stems = processor.process_local_file(
                        source, output_format=output_format
                    )
                job_status['output_files'].extend(stems.values())

        except Exception as e:
            print(f"Error processing {label}: {e}", file=sys.stderr)
            job_status['error'] = f"Failed on item {i+1}: {e}"
            job_status['is_running'] = False
            return

        # Update progress after successful completion
        job_status['progress'] = i + 1
        job_status['percentage'] = round((i + 1) / len(sources) * 100)

    job_status['is_running'] = False
    job_status['current_task'] = "All tasks completed!"
    job_status['percentage'] = 100


# --- Routes ---
@app.route('/')
def index():
    """Main page with the URL input form."""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    """
    Receives form data, calculates estimates, and shows a confirmation page.
    """
    urls_text = request.form.get('urls', '')
    action = request.form.get('action', '')
    output_format = request.form.get('output_format', 'mp3').lower()
    audio_file = request.files.get('audio_file')

    urls = [url.strip() for url in urls_text.splitlines() if url.strip()]

    if action not in VALID_ACTIONS:
        return "Please select a valid action.", 400
    if output_format not in OUTPUT_FORMATS:
        return "Please select MP3 or WAV as output format.", 400

    uploaded_files = []
    if audio_file and audio_file.filename:
        safe_name = secure_filename(audio_file.filename)
        extension = Path(safe_name).suffix.lower()
        requested_format = request.form.get('input_format', 'auto').lower()
        if not safe_name or extension not in SUPPORTED_AUDIO_EXTENSIONS:
            supported = ', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
            return f"Unsupported audio file. Supported formats: {supported}", 400
        if requested_format != 'auto' and extension != f'.{requested_format}':
            return "The selected audio type does not match the file extension.", 400
        UPLOAD_DIR.mkdir(exist_ok=True)
        stored_name = f'{uuid.uuid4().hex}_{safe_name}'
        audio_file.save(UPLOAD_DIR / stored_name)
        uploaded_files.append(stored_name)

    if (not urls and not uploaded_files) or not action:
        return "Please provide at least one YouTube URL or MP3 and select an action.", 400

    model = 'htdemucs_ft' # Default for karaoke and 4-stem
    if action == '6-stem':
        model = 'htdemucs_6s'
    elif action in ('bs-6-stem', 'guitar-karaoke'):
        model = 'bs-roformer-sw-6s'
    elif action == 'vocal-choir':
        model = 'htdemucs_ft + UVR-BVE'

    estimate_model = (
        'htdemucs_6s'
        if action in ('bs-6-stem', 'guitar-karaoke')
        else 'htdemucs_ft' if action == 'vocal-choir' else model
    )
    return render_template(
        'confirm.html', urls=urls, uploaded_files=uploaded_files,
        action=action, model=model, output_format=output_format,
        estimate_model=estimate_model
    )


@app.route('/estimate', methods=['POST'])
def estimate():
    """
    Asynchronously estimates processing time.
    """
    urls_text = request.json.get('urls', '')
    model = request.json.get('model', 'htdemucs_ft')
    urls = [url.strip() for url in urls_text.splitlines() if url.strip()]

    if not urls:
        return jsonify({'error': 'No URLs provided'}), 400

    total_duration = 0
    smart_processor = SmartProcessor(verbose=False)
    for url in urls:
        duration = smart_processor.get_youtube_duration(url)
        if duration:
            total_duration += duration

    estimate_data = smart_processor.estimate_processing_time(total_duration, model)
    return jsonify(estimate_data)



@app.route('/run', methods=['POST'])
def run():
    """
    Starts the background processing job.
    """
    global job_status
    if job_status['is_running']:
        return "A job is already in progress.", 400

    urls_text = request.form.get('urls', '')
    uploaded_files = request.form.getlist('uploaded_files')
    action = request.form.get('action', '')
    model = request.form.get('model', 'htdemucs_ft')
    output_format = request.form.get('output_format', 'mp3').lower()

    if action not in VALID_ACTIONS:
        return "Please select a valid action.", 400
    if output_format not in OUTPUT_FORMATS:
        return "Please select MP3 or WAV as output format.", 400

    urls = [url.strip() for url in urls_text.splitlines() if url.strip()]

    for filename in uploaded_files:
        if Path(filename).name != filename or not (UPLOAD_DIR / filename).is_file():
            return "Invalid or missing uploaded file.", 400
    if not urls and not uploaded_files:
        return "No input was provided.", 400

    # For simplicity, we'll assume high performance is false.
    # This could be a user option.
    high_performance = False

    # Start the background thread
    thread = threading.Thread(
        target=run_processing_job,
        args=(urls, uploaded_files, action, model, output_format,
              high_performance)
    )
    thread.daemon = True
    thread.start()

    return redirect(url_for('progress_page'))

@app.route('/progress')
def progress_page():
    """Displays the progress of the running job."""
    return render_template('progress.html')

@app.route('/status')
def status():
    """API endpoint to get the current job status."""
    global job_status
    return jsonify(job_status)

@app.route('/results')
def results():
    """Displays the final list of output files."""
    global job_status
    # This is a simplified results page.
    # In a real app, you'd pass job results more robustly.
    return render_template('results.html', files=job_status['output_files'])


@app.route('/outputs/<path:filepath>')
def download_file(filepath):
    """
    Serves files from the project's root output directories.
    """
    return send_from_directory('.', filepath, as_attachment=True)



if __name__ == '__main__':
    # Ensure output directories exist
    Path('downloads').mkdir(exist_ok=True)
    Path('separated').mkdir(exist_ok=True)
    Path('karaoke').mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(exist_ok=True)
    app.run(
        debug=os.getenv('FLASK_DEBUG') == '1',
        host='0.0.0.0',
        port=5001
    )
