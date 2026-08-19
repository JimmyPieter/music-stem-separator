# Music Stem Separator

Een lokale webapp voor het downloaden, converteren en scheiden van muziek met
Demucs en BS-RoFormer.

## Mogelijkheden

- YouTube-audio downloaden met automatische 403-fallback.
- Lokale audio uploaden: MP3, WAV, FLAC, M4A, AAC, OGG, OPUS en WMA.
- Uitvoer kiezen als MP3 of WAV.
- Normale karaoke: zang verwijderen.
- Leadzang en achtergrondkoor apart maken met UVR-BVE.
- Gitaar karaoke: met BS-RoFormer alles behalve de gitaarlijn combineren.
- Scheiden in 4 of 6 stems.
- Automatische NVIDIA/CUDA-detectie met CPU-fallback.

## Installatie

Vereist: Python 3.11, FFmpeg en bij voorkeur een NVIDIA-GPU.

```powershell
setup.bat
```

Of handmatig:

```powershell
py -3.11 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

Deno is nodig voor recente YouTube-beveiligingscontroles en moet via `PATH` of
de bestaande WinGet-installatie gevonden kunnen worden.

## Gebruik via de GUI

```powershell
venv\Scripts\python.exe app.py
```

Open daarna [http://127.0.0.1:5001](http://127.0.0.1:5001).

1. Plak YouTube-links of kies een lokaal audiobestand.
2. Laat het invoerformaat automatisch herkennen of selecteer het expliciet.
3. Kies MP3 of WAV als uitvoerformaat.
4. Kies de verwerking, controleer de samenvatting en start de taak.
5. Download de resultaten op de resultatenpagina.

De GUI is de normale gebruikersroute. De losse Python-modules zijn interne
onderdelen en zijn niet nodig voor dagelijks gebruik.

## Verwerkingsopties

| Optie | Resultaat |
|---|---|
| Download | YouTube-audio downloaden of een upload converteren |
| Zang karaoke | Instrumentale versie zonder vocals, plus vocals |
| Zang & koor scheiden | Lead vocals, backing vocals en instrumental |
| 4 stems | Vocals, drums, bass en other |
| 6 stems | Vocals, drums, bass, guitar, piano en other met Demucs |
| BS-RoFormer 6 stems | Zes losse stems met BS-RoFormer |
| Gitaar karaoke | Eén mix met alles behalve de guitar-stem |

## Uitvoermappen

- `downloads/`: downloads en conversies
- `separated/`: losse stems
- `karaoke/`: karaoke-uitvoer
- `uploads/`: lokale bronbestanden

## Problemen oplossen

- **Wijziging niet zichtbaar:** stop met `Ctrl+C`, start `app.py` opnieuw en
  vernieuw de browser.
- **YouTube HTTP 403:** controleer of de actuele server draait; de downloader
  gebruikt een embedded-clientfallback voor geweigerde streams.
- **CUDA-geheugen vol:** sluit andere GPU-programma's. CPU werkt ook, maar is
  aanzienlijk trager.
- **FFmpeg ontbreekt:** installeer FFmpeg, voeg het toe aan `PATH` en herstart de
  terminal en server.
