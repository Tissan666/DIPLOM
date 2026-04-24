# Review Integrity Dashboard Frontend

Modern React + TypeScript frontend for the diploma project on review manipulation detection.

## Stack

- React
- TypeScript
- Tailwind CSS
- Framer Motion
- Recharts
- lucide-react
- Vite

## Development

Start the Flask API first:

```powershell
cd "C:\DIPLOM XD"
python app.py
```

Then run the React dashboard in a second terminal:

```powershell
cd "C:\DIPLOM XD\frontend"
npm install
npm run dev
```

The Vite dev server proxies `/api`, `/predict`, and `/health` to `http://127.0.0.1:5000`.

## Production build

```powershell
cd "C:\DIPLOM XD\frontend"
npm run build
```

After the build, Flask can serve the generated files from `frontend/dist/` automatically.
