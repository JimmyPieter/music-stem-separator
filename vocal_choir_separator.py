"""Two-stage separation of lead vocals, backing vocals, and instrumental."""

import os
import shutil
from pathlib import Path

import ffmpeg
from audio_separator.separator import Separator

from music_processor import MusicProcessor
from youtube_downloader import YouTubeAudioDownloader


BACKING_VOCALS_MODEL = 'UVR-BVE-4B_SN-44100-2.pth'


class VocalChoirProcessor:
    """Split a song into lead vocals, backing vocals, and instrumental."""

    def __init__(self, download_dir='downloads', output_dir='karaoke/vocal_choir',
                 model_dir='models/audio-separator', device=None,
                 high_performance=False, progress_callback=None):
        self.downloader = YouTubeAudioDownloader(
            output_dir=download_dir, format='mp3', quality='320'
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.device = device
        self.high_performance = high_performance
        self.progress_callback = progress_callback

    def _report_progress(self, percentage, message):
        if self.progress_callback:
            self.progress_callback(percentage, message)

    @staticmethod
    def _copy_or_convert(source, destination, output_format):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if output_format == 'wav':
            shutil.copy2(source, destination)
        else:
            ffmpeg.output(
                ffmpeg.input(str(source)).audio,
                str(destination), audio_bitrate='320k'
            ).overwrite_output().run(quiet=True)

    def process_local_file(self, audio_file, output_format='mp3'):
        audio_path = Path(audio_file)
        if not audio_path.is_file():
            raise FileNotFoundError(f'Audio file not found: {audio_file}')
        if output_format not in ('mp3', 'wav'):
            raise ValueError('Output format must be mp3 or wav')

        self._report_progress(5, 'Extracting all vocals from the music...')
        first_stage = MusicProcessor(
            model='htdemucs_ft', device=self.device,
            output_dir='separated', high_performance=self.high_performance
        )
        stems = first_stage.process_local_file(
            audio_path, two_stems='vocals', output_format='wav'
        )
        vocals_path = Path(stems['vocals'])
        instrumental_path = Path(stems['no_vocals'])

        song_output_dir = self.output_dir / audio_path.stem
        song_output_dir.mkdir(parents=True, exist_ok=True)
        extension = output_format.lower()
        final_instrumental = song_output_dir / f'instrumental.{extension}'
        self._copy_or_convert(
            instrumental_path, final_instrumental, output_format
        )

        self._report_progress(55, 'Loading lead/backing vocals model...')
        separator = Separator(
            model_file_dir=str(self.model_dir),
            output_dir=str(song_output_dir),
            output_format=output_format.upper(),
            output_bitrate='320k' if output_format == 'mp3' else None,
            use_autocast=True,
        )
        separator.load_model(BACKING_VOCALS_MODEL)
        self._report_progress(65, 'Separating lead vocals and backing vocals...')
        output_names = separator.separate(
            str(vocals_path),
            custom_output_names={
                # UVR-BVE internally exposes these as Vocals/Instrumental,
                # while semantically they are lead/backing vocals.
                'Vocals': 'lead_vocals',
                'Instrumental': 'backing_vocals',
                'Lead Vocals': 'lead_vocals',
                'Backing Vocals': 'backing_vocals',
            },
        )
        if len(output_names) != 2:
            raise RuntimeError(
                'Lead/backing vocals model did not produce both expected stems'
            )
        outputs = {
            Path(name).stem: (song_output_dir / name).as_posix()
            for name in output_names
        }
        outputs['instrumental'] = final_instrumental.as_posix()
        self._report_progress(100, 'Lead vocals and backing vocals complete')
        return outputs

    def process_from_youtube(self, url, output_format='mp3',
                             keep_original=False):
        self._report_progress(1, 'Downloading audio...')
        downloaded_file = self.downloader.download(url)
        try:
            return self.process_local_file(
                downloaded_file, output_format=output_format
            )
        finally:
            if not keep_original and Path(downloaded_file).exists():
                os.remove(downloaded_file)
