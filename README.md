# Dropbox Uploader

A command-line Dropbox uploader with an interactive folder browser, built for Termux and desktop use.

## Background

This project was born out of frustration. My old phone running Android 10 could upload files to Dropbox reliably — both through the browser and the official app. My new phone running Android 16 can't. Uploads drop, connections get cut, transfers fail mid-way. The culprit is a slow internet connection at 900 kbps, and neither the Dropbox app nor the browser handles it gracefully at that speed. This script does.

## Requirements

```
pip install requests
```

## Token setup

Create a file `h.txt` in the same folder as the script and paste your Dropbox Access Token into it:

```
sl.AbCdEfGhIjKlMnOpQrStUvWxYz...
```

Get your token at [dropbox.com/developers/apps](https://www.dropbox.com/developers/apps) → create an app → generate an **Access Token**.

## Usage

```bash
# Single file – interactive destination picker
python dbx_upload.py video.mp4

# Multiple files
python dbx_upload.py photo.jpg document.pdf archive.zip

# Entire folder
python dbx_upload.py /sdcard/Photos

# Folder with destination specified (skips the browser)
python dbx_upload.py files/ --dest /Backup/2025
```

## Output

```
[1/3]
→ /sdcard/video.mp4  (1.2 GB)
  Destination: /Backup/video.mp4
  47.3 MB / 1.2 GB   8.2 MB/s   0:05 / ~2:23
  ✓ Done
```

The progress line shows: **sent / total — speed — elapsed / estimated remaining**

## Upload behaviour

| File size | Method |
|---|---|
| under 150 MB | single upload |
| over 150 MB | chunked upload in 100 MB pieces |

Existing files in Dropbox are **overwritten** (`mode: overwrite`).
