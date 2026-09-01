# Trainspotting React UI

This client recreates the CRUD features in `web/` with React. During
development, Vite forwards requests beginning with `/api` to the FastAPI
server at `http://127.0.0.1:8000`.

Run FastAPI from the repository root:

```bash
.venv/bin/uvicorn app.main:app --reload
```

In a second terminal, run React:

```bash
cd react-ui
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

Useful checks:

```bash
npm run lint
npm run build
```

---

*(h)gaines.*
