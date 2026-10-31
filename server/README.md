# Code68 Cloud Inference Server (Kaggle / Remote GPU)

This directory contains the remote cloud inference server for Code68, enabling **Cloud Intelligence + Local Execution**.

The LLM runs remotely on a GPU-powered instance (such as Kaggle with 2x NVIDIA Tesla T4 GPUs), exposing an authenticated OpenAI-compatible API over a secure tunnel. The local Code68 agent connects to this endpoint to execute actions on the developer's computer.

---

## 1. Kaggle Notebook Quickstart

1. Open a new Kaggle Notebook: [https://www.kaggle.com/code](https://www.kaggle.com/code)
2. In the right panel, select **Accelerator: GPU T4 x 2**.
3. In the first cell, install dependencies:
   ```bash
   !pip install -q fastapi uvicorn "transformers>=4.40.0" accelerate bitsandbytes pycloudflared
   ```
4. Copy `kaggle_server.py` into a notebook cell or upload it.
5. Set your secret API key:
   ```python
   import os
   os.environ["CODE68_API_KEY"] = "my-secret-key-12345"
   os.environ["MODEL_ID"] = "Qwen/Qwen2.5-Coder-7B-Instruct"
   ```
6. Run the server:
   ```python
   !python kaggle_server.py
   ```
7. The output will print your public tunnel URL:
   ```
   ============================================================
   CODE68 PUBLIC TUNNEL URL: https://random-name.trycloudflare.com/v1
   Set this in your local terminal:
   export CODE68_BASE_URL=https://random-name.trycloudflare.com/v1
   export CODE68_API_KEY=my-secret-key-12345
   ============================================================
   ```

---

## 2. Connect Your Local Code68 Agent

On your local development machine:

```bash
# In your terminal or in .env:
export CODE68_BASE_URL="https://random-name.trycloudflare.com/v1"
export CODE68_API_KEY="my-secret-key-12345"

# Run Code68:
code68
```

---

## 3. Alternative Hosting Backends

Because Code68 uses standard OpenAI-compatible endpoints, you can substitute Kaggle with any provider without modifying the CLI:

- **vLLM / Ollama** on local or cloud GPUs
- **OpenRouter / DeepInfra / Together AI**
- **RunPod / Lambda Labs / Vast.ai**
