# Music Stem Separator starten

De webinterface is de hoofdinterface van deze applicatie.

## Vereisten

- Python 3.11
- FFmpeg
- Deno voor YouTube JavaScript-controles
- Optioneel: NVIDIA-GPU met CUDA

## Eerste installatie

```powershell
setup.bat
```

Handmatig:

```powershell
py -3.11 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Iedere keer starten

```powershell
venv\Scripts\python.exe app.py
```

Ga naar [http://127.0.0.1:5001](http://127.0.0.1:5001). Laat PowerShell open
zolang je de GUI gebruikt. Regels zoals `GET /status 200` zijn normale
voortgangscontroles vanuit de browser, geen fouten.

## Invoer en uitvoer

De GUI accepteert YouTube-links en MP3, WAV, FLAC, M4A, AAC, OGG, OPUS en WMA.
Automatische invoerherkenning is aanbevolen. Kies MP3 voor kleinere bestanden of
WAV voor verliesvrije uitvoer. Deze keuze geldt voor downloads, conversies,
karaoke en losse stems.

De actie **Zang & koor scheiden** maakt `lead_vocals`, `backing_vocals` en
`instrumental`. Het UVR-BVE-model (ongeveer 224 MB) wordt bij het eerste gebruik
automatisch gedownload en daarna lokaal hergebruikt.

## Stoppen en herstarten

Stop met `Ctrl+C`. Start daarna opnieuw met hetzelfde `app.py`-commando. Een
herstart is vereist na wijzigingen aan Python- of templatebestanden.

## Problemen oplossen

- **HTTP 403:** herstart de server zodat de actuele YouTube-fallback geladen is.
- **FFmpeg ontbreekt:** voeg FFmpeg toe aan `PATH` en open PowerShell opnieuw.
- **Onvoldoende GPU-geheugen:** sluit andere GPU-applicaties; CPU is langzamer
  maar blijft beschikbaar.
- **GUI blijft verwerken:** zoek in PowerShell naar de eerste exception boven de
  normale `GET /status 200`-regels.
