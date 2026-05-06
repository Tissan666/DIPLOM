# Review Integrity Console

Review Integrity Console detects suspicious product reviews and rating manipulation with a hybrid anti-fraud pipeline and a React dashboard for investigation.

## What the system does

1. Accepts a product URL, raw HTML, or structured rating records.
2. Collects or parses review content.
3. Scores review text with a neural classifier.
4. Adds page-level manipulation heuristics such as duplicate text, rating bursts, and author concentration.
5. Runs a second anomaly detector for full site-level rating datasets with user, item, timestamp, IP, and geolocation fields.
6. Returns structured JSON for dashboards, moderation workflows, and CLI use.

## Project structure

```text
C:\DIPLOM XD
|-- app.py
|-- collect_reviews.py
|-- detect.py
|-- run_dev.py
|-- train.py
|-- requirements.txt
|-- README.md
|-- data/
|-- examples/
|-- fake_rating_detector/
|-- frontend/
|   |-- src/
|   |-- package.json
|   `-- vite.config.ts
|-- models/
|-- outputs/
`-- review_scraper_detector/
```

## Installation

```powershell
cd "C:\DIPLOM XD"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Optional external HTML fetching:

```powershell
$env:SCRAPINGBEE_API_KEY="your_api_key_here"
$env:SCRAPEDO_API_KEY="your_scrapedo_token_here"
```

Optional authenticated marketplace API:

```powershell
$env:WB_FEEDBACKS_API_KEY="your_wildberries_feedbacks_token"
```

URL mode tries collectors in this order:

1. Marketplace API, when supported. Wildberries can use the public `imtId` feedback endpoint, or the official seller feedback API when `WB_FEEDBACKS_API_KEY` is configured.
2. Local Playwright collector, which renders the page, opens/scrolls reviews, and extracts DOM/network/SPA-state reviews.
3. External HTML collectors: ScrapingBee first, then Scrape.do as a fallback when `SCRAPEDO_API_KEY` is configured.

For Ozon, Yandex Market, AliExpress, MegaMarket, Lamoda, DNS, Citilink, M.Video, Eldorado, Avito, Detmir, Gold Apple, Sima-land, Amazon, eBay, Temu, SHEIN and similar public storefronts, the API step reports the exact limitation when no stable unauthenticated review API is configured, then continues to Playwright and external HTML fallbacks.

## Training

The review text model expects a CSV with:

- `review_text`
- `rating`
- `label`

Where:

- `label = 0` means a normal review
- `label = 1` means a suspicious review

Default training can combine local archives, UCI data, and synthetic suspicious examples:

```powershell
.venv\Scripts\python.exe -m train --regenerate-sample
```

Larger public-data run:

```powershell
python train.py --include-large-public-data --max-rows-per-source 3000 --large-max-rows-per-source 20000 --synthetic-ratio 0.75 --epochs 24 --batch-size 64 --learning-rate 0.0008 --review-max-features 12000 --review-char-max-features 6000 --review-hidden-dims 768,256,64 --review-dropout 0.30 --skip-ratings-model
```

This mode can ingest:

- `McAuley-Lab/Amazon-Reviews-2023` from Hugging Face
- Yelp Open Dataset from a local download
- YelpNYC labeled data from a local file

If you want only the synthetic fallback dataset:

```powershell
.venv\Scripts\python.exe -m train --no-external-data --regenerate-sample
```

Generated artifacts usually include:

- `models/review_text_classifier.pt`
- `models/review_text_bundle.joblib`
- `models/autoencoder.pt`
- `models/pipeline.joblib`
- `outputs/review_metrics.json`
- `outputs/review_training_history.json`
- `outputs/review_training_summary.json`
- `outputs/system_training_summary.json`

## Evaluation

Run model evaluation without retraining:

```powershell
.venv\Scripts\python.exe evaluate.py --review-dataset data\combined_review_training.csv --ratings-dataset data\sample_ratings.csv
```

For a faster smoke evaluation:

```powershell
.venv\Scripts\python.exe evaluate.py --review-dataset data\combined_review_training_smoke.csv --ratings-dataset data\sample_ratings.csv --output-dir outputs\evaluation_smoke
```

Evaluation reports are written under `outputs/evaluation/` or the selected output directory:

- `evaluation_summary.json`
- `review_model_evaluation.json`
- `rating_model_evaluation.json`

The reports include precision, recall, F1, ROC-AUC, PR-AUC, confusion matrix, calibration bins, expected calibration error, Brier score, threshold profiles, source/product/language/length slices, false-positive and false-negative examples, robustness probes, triage summaries, and practical recommendations.

## Review collection

The Playwright collector renders public pages, scrolls review feeds, exports JSON and CSV, and stops on captcha, `403`, or `429` instead of bypassing access controls.

Install the browser once:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

Smoke-test Playwright on the bundled sample page:

```powershell
$sampleUrl = "file:///" + ((Resolve-Path examples\sample_product_reviews.html).Path -replace "\\", "/")
.venv\Scripts\python.exe collect_reviews.py $sampleUrl --marketplace generic --max-reviews 10 --headless --output-dir outputs\playwright_smoke
```

Run collection:

```powershell
.venv\Scripts\python.exe collect_reviews.py "https://example.com/product-page" --marketplace generic --max-reviews 200 --headless
```

For marketplace debugging, headed mode is often easier:

```powershell
.venv\Scripts\python.exe collect_reviews.py "https://example.com/product-page" --marketplace wildberries --max-reviews 200
```

AliExpress pages usually load reviews through dynamic widgets/API calls, so use the dedicated adapter and start with visible Chromium when checking a real product URL:

```powershell
.venv\Scripts\python.exe collect_reviews.py "https://www.aliexpress.com/item/PRODUCT_ID.html" --marketplace aliexpress --max-reviews 200
```

The collector records public data only. If AliExpress returns a login wall, captcha, 403, or 429, collection stops and reports the barrier instead of trying to bypass it.

Collector outputs are saved under `outputs/collected_reviews/`.

## CLI analysis

Local HTML snapshot:

```powershell
.venv\Scripts\python.exe -m detect --html-file examples/sample_product_reviews.html
```

Public product page URL:

```powershell
.venv\Scripts\python.exe -m detect "https://example.com/product-page"
```

Optional API controls:

```powershell
.venv\Scripts\python.exe -m detect "https://example.com/product-page" --country-code us --wait-ms 2000
```

Default JSON output:

- `outputs/scraped_review_predictions.json`

## Frontend development

Recommended local workflow:

```powershell
cd "C:\DIPLOM XD"
python run_dev.py
```

This starts:

- Flask API on `http://127.0.0.1:5000`
- React dashboard on `http://127.0.0.1:5173`

`run_dev.py` automatically runs `npm install` when frontend dependencies are missing or older than `package.json` / `package-lock.json`. To skip that check:

```powershell
python run_dev.py --skip-install
```

Before a defense, release, or GitHub push, run the combined local check:

```powershell
python check_project.py
```

It compiles the Python modules and builds the React frontend.

For a backend-only smoke check:

```powershell
python check_backend.py
```

It verifies `/health`, model artifact compatibility, OCR/CLIP image-analysis diagnostics, request validation, inline HTML analysis, unsafe image-source filtering, structured rating-record analysis, and saved-report history.

URL mode first tries the project-owned public API and Playwright collectors, then external collectors. It can still be affected by marketplace bot protection, credits, browser availability, or proxy availability. For stable demos and defense runs, use HTML snapshot or structured-file mode when a live marketplace page is unavailable.

Successful `/api/predict` calls are saved to a local SQLite database under `outputs/analysis_history.sqlite3` by default. The history API is available at:

- `GET /api/history`
- `GET /api/history/<report_id>`

To store history somewhere else, set:

```powershell
$env:ANALYSIS_HISTORY_DB_PATH="C:\path\to\analysis_history.sqlite3"
```

`/health` also reports optional photo-analysis readiness under `vision_capabilities`:

- `ocr.status=ready` means Python OCR dependencies and the Tesseract engine are available.
- `ocr.status=engine_unavailable` usually means `pytesseract` is installed, but the Tesseract executable is not installed or is not on `PATH`.
- `image_alignment.status=dependencies_ready` means the CLIP/ViT Python dependencies are available. Set `REVIEW_IMAGE_ALIGNMENT_HEALTH_LOAD=1` if you also want `/health` to verify model loading/cache.

On Windows, if Tesseract is installed but not available through `PATH`, point the backend at the executable:

```powershell
$env:TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
$env:REVIEW_IMAGE_OCR_LANG="eng+rus"
```

If you want to run services separately, start the backend:

```powershell
.venv\Scripts\python.exe app.py
```

Then start the frontend:

```powershell
cd "C:\DIPLOM XD\frontend"
npm install
npm run dev
```

The React dashboard supports:

- URL analysis
- raw HTML analysis
- site-data ingestion from JSON, CSV, Excel, HTML, and API responses
- summary cards and explainability views
- suspicious review and suspicious user inspection

## Production frontend build

Build the React frontend:

```powershell
cd "C:\DIPLOM XD\frontend"
npm install
npm run build
```

If `frontend/dist/` exists, Flask serves the built dashboard at `http://127.0.0.1:5000/`.
If it does not exist, the root route returns a small instruction page and the API remains available.

## API endpoints

- `GET /`
- `GET /health`
- `POST /predict`
- `POST /api/predict`

Example URL request:

```json
{
  "url": "https://example.com/product-page",
  "api_key": "your_api_key_here",
  "render_js": true,
  "country_code": "us",
  "wait_ms": 5000
}
```

Example HTML request:

```json
{
  "html": "<html>...</html>",
  "source_url": "inline-html"
}
```

Example records request:

```json
{
  "records": [
    {
      "user_id": "u1",
      "item_id": "item1",
      "rating": 5,
      "timestamp": "2025-01-01T10:00:00",
      "ip_address": "1.1.1.1",
      "geo_country": "Russia",
      "geo_city": "Samara",
      "review_text": "Amazing!"
    }
  ]
}
```
