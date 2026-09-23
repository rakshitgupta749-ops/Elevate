# Running Elevate

Follow these instructions to run the Elevate prototype locally.

## 1. Run the Backend

Open a terminal, navigate to the `backend` folder, and start the FastAPI server:

```powershell
cd backend
uvicorn app.main:app --reload
```

The backend API will be available at `http://127.0.0.1:8000`.

*Note: Ensure your `TCS_API_KEY` is set in the `backend/.env` file.*

## 2. Run the Frontend

Open a second terminal, navigate to the `frontend` folder, and start the Vite development server:

```powershell
cd frontend
npm run dev
```

The frontend app will be available at `http://localhost:5173`.
