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
```

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

## Review collection

The Playwright collector renders public pages, scrolls review feeds, exports JSON and CSV, and stops on captcha, `403`, or `429` instead of bypassing access controls.

Install the browser once:

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

Run collection:

```powershell
python collect_reviews.py "https://example.com/product-page" --marketplace generic --max-reviews 200
```

For marketplace debugging, headed mode is often easier:

```powershell
python collect_reviews.py "https://example.com/product-page" --marketplace wildberries --max-reviews 200
```

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
