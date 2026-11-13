# Running Elevate

Follow these instructions to run the Elevate prototype locally.

## Quick Start (Automated)

### Windows (PowerShell)
Run both backend and frontend servers simultaneously using:

```powershell
.\run.ps1
```

> **Tip**: To launch each server in its own separate console window, run:
> ```powershell
> .\run.ps1 -SeparateWindows
> ```
> If script execution is restricted on your machine, run:
> ```powershell
> powershell -ExecutionPolicy Bypass -File .\run.ps1
> ```

### Linux / macOS (Bash)
Run both servers simultaneously using:

```bash
chmod +x run.sh
./run.sh
```

---

## Manual Start (Two Terminals)

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
