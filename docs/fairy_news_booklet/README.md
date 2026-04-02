# Fairy News booklet (Word)

Educational DOCX with screenshots of the live UI and short essays on benefits
for young and adult readers.

Build (server on port 8765, reports saved):

```powershell
$env:FAIRYNEWS_SAVE_REPORTS='1'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

```powershell
python scripts/build_fairy_news_booklet.py --port 8765
```

Output: `docs/fairy_news_booklet/Fairy_News_Booklet.docx`, PNGs under `png/`.
Rebuild text only from existing PNGs: `--skip-capture`.
