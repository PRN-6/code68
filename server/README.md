# Code68 Cloud Inference Server

Runs **Qwen2.5-Coder-7B-Instruct** (4-bit quantized) on Kaggle's free GPUs and exposes an OpenAI-compatible API via a Cloudflare tunnel.

## Quick Start on Kaggle

### Option A: Upload the Notebook (Recommended)

1. Go to [kaggle.com/code](https://www.kaggle.com/code) → **New Notebook**
2. **File → Import Notebook** → upload `code68_kaggle.ipynb`
3. In the right sidebar → **Settings**:
   - Accelerator = **GPU T4 x 2**
   - Internet = **ON**
4. Click **Run All**
5. Wait ~2 minutes for the model to load
6. Copy the tunnel URL from the output

### Option B: Copy-Paste (3 Cells)

1. Create a new Kaggle notebook (GPU T4 x 2, Internet ON)
2. **Cell 1** — install dependencies:
   ```
   !pip install -q fastapi uvicorn "transformers>=4.40.0" accelerate bitsandbytes pycloudflared
   ```
3. **Cell 2** — write the server script (the `%%writefile` line MUST be the first line):
   ```
   %%writefile /kaggle/working/code68_server.py
   import os, json, time, uuid, asyncio
   ...
   ```
   Copy the full Cell 2 content from `kaggle_notebook.py` (the text inside the triple-quoted block).

4. **Cell 3** — start the server:
   ```
   !python /kaggle/working/code68_server.py
   ```

### What You'll See

```
Loading Qwen/Qwen2.5-Coder-7B-Instruct in 4-bit quantization...
Model loaded on: Tesla T4
============================================================
CODE68 TUNNEL URL: https://xxxx-xxxx.trycloudflare.com/v1

On your LOCAL machine, set these in your .env file:
  CODE68_BASE_URL=https://xxxx-xxxx.trycloudflare.com/v1
  CODE68_API_KEY=code68-secret-key
============================================================
```

## Local Setup

On your local machine, create or edit `.env` in your project directory:

```env
CODE68_BASE_URL=https://xxxx-xxxx.trycloudflare.com/v1
CODE68_API_KEY=code68-secret-key
```

Then verify the connection:

```bash
code68 doctor
```

You should see `LLM Endpoint: Connected` in the output.

## Local Dev/Mock Server

For local development without a GPU, use `kaggle_server.py` directly:

```bash
pip install fastapi uvicorn
python server/kaggle_server.py
```

This runs in **mock mode** (no real model) and returns canned responses — useful for testing the CLI and agent loop locally.

Set `.env` to point to it:

```env
CODE68_BASE_URL=http://localhost:8000/v1
CODE68_API_KEY=code68-secret-key
```

## Files

| File | Purpose |
|------|---------|
| `code68_kaggle.ipynb` | Ready-to-upload Kaggle notebook |
| `kaggle_notebook.py` | Same content as plain text (for reference/copy-paste) |
| `kaggle_server.py` | Standalone server (works locally in mock mode, or on any GPU machine) |
| `requirements-server.txt` | Server-only dependencies |

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| GET | `/v1/models` | Bearer token | List available models |
| POST | `/v1/chat/completions` | Bearer token | Chat completions (streaming/non-streaming) |

## Security

- All `/v1/*` endpoints require `Authorization: Bearer <API_KEY>` header
- Default key is `code68-secret-key` — change it via `CODE68_API_KEY` environment variable
- The tunnel URL changes each time the notebook restarts

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No module named 'fastapi'" | Run Cell 1 first to install dependencies |
| "No such file or directory" | Run Cell 2 first to write the server script |
| Model loading hangs | Ensure GPU T4 x 2 is selected, not CPU |
| Tunnel URL not showing | Ensure Internet is ON in notebook settings |
| `code68 doctor` says "unreachable" | Check that the Kaggle notebook cell is still running |
