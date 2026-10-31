# ============================================================
# CODE68 — Kaggle Cloud Inference Server
# ============================================================
#
# INSTRUCTIONS FOR KAGGLE:
# ========================
#
# Option A (Recommended): Upload the .ipynb file
#   1. Go to https://www.kaggle.com/code → "New Notebook"
#   2. File → Import Notebook → upload "code68_kaggle.ipynb"
#   3. Settings (right sidebar) → Accelerator = "GPU T4 x 2"
#   4. Settings → Internet = ON
#   5. Run all cells. Copy the tunnel URL into your local .env.
#
# Option B: Copy-paste into 3 separate Kaggle cells
#   1. Create a new Kaggle notebook
#   2. Settings → GPU T4 x 2, Internet ON
#   3. Paste CELL 1 content into the first cell, run it
#   4. Paste CELL 2 content into a new cell, run it
#   5. Paste CELL 3 content into a new cell, run it
#   6. Copy the tunnel URL into your local .env file
#
# ============================================================


# ----- CELL 1: Paste this into the FIRST notebook cell -----

# !pip install -q fastapi uvicorn "transformers>=4.40.0" accelerate bitsandbytes pycloudflared


# ----- CELL 2: Paste EVERYTHING below into the SECOND cell -----
# (The %%writefile line MUST be the very first line of the cell)

"""
%%writefile /kaggle/working/code68_server.py
import os, json, time, uuid, asyncio
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import torch

API_KEY = os.getenv("CODE68_API_KEY", "code68-secret-key")
MODEL_ID = os.getenv("CODE68_MODEL_ID", "Qwen/Qwen2.5-Coder-7B-Instruct")
PORT = 8000

app = FastAPI(title="Code68 Cloud LLM Server")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

def verify_api_key(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization format")
    if parts[1] != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return parts[1]

class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: float = 0.2
    max_tokens: Optional[int] = 2048
    stream: bool = True
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = "auto"

model_ref = None
tokenizer_ref = None

def load_model():
    global model_ref, tokenizer_ref
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    print(f"Loading {MODEL_ID} in 4-bit quantization...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
    )
    tokenizer_ref = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model_ref = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, quantization_config=bnb_config,
        device_map="auto", torch_dtype=torch.float16, trust_remote_code=True,
    )
    print(f"Model loaded on: {torch.cuda.get_device_name(0)}")

@app.get("/health")
def health():
    return {"status": "ok", "gpu": torch.cuda.get_device_name(0), "model": MODEL_ID}

@app.get("/v1/models")
def list_models(auth: str = Depends(verify_api_key)):
    return {
        "object": "list",
        "data": [{"id": MODEL_ID, "object": "model", "created": int(time.time()), "owned_by": "code68"}],
    }

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, auth: str = Depends(verify_api_key)):
    if model_ref is None:
        raise HTTPException(503, "Model is still loading")
    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    hf_messages = []
    for m in req.messages:
        d = {"role": m.role, "content": m.content or ""}
        if m.name: d["name"] = m.name
        if m.tool_call_id: d["tool_call_id"] = m.tool_call_id
        if m.tool_calls: d["tool_calls"] = m.tool_calls
        hf_messages.append(d)

    try:
        if req.tools and hasattr(tokenizer_ref, "apply_chat_template"):
            text = tokenizer_ref.apply_chat_template(
                hf_messages, tools=req.tools, tokenize=False, add_generation_prompt=True,
            )
        else:
            text = tokenizer_ref.apply_chat_template(
                hf_messages, tokenize=False, add_generation_prompt=True,
            )
    except Exception:
        text = "\\n".join(f"{m['role'].upper()}: {m['content']}" for m in hf_messages) + "\\nASSISTANT: "

    model_inputs = tokenizer_ref([text], return_tensors="pt").to(model_ref.device)

    if req.stream:
        async def event_stream():
            from transformers import TextIteratorStreamer
            from threading import Thread
            streamer = TextIteratorStreamer(tokenizer_ref, skip_prompt=True, skip_special_tokens=False)
            gen_kwargs = dict(
                model_inputs, streamer=streamer,
                max_new_tokens=req.max_tokens or 2048,
                temperature=max(req.temperature, 0.01),
                do_sample=req.temperature > 0,
            )
            Thread(target=model_ref.generate, kwargs=gen_kwargs).start()
            for chunk_text in streamer:
                chunk = {
                    "id": request_id, "object": "chat.completion.chunk",
                    "created": int(time.time()), "model": req.model,
                    "choices": [{"index": 0, "delta": {"content": chunk_text}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk)}\\n\\n"
                await asyncio.sleep(0.001)
            yield f"data: {json.dumps({'id': request_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': req.model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\\n\\n"
            yield "data: [DONE]\\n\\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        gen_ids = model_ref.generate(
            **model_inputs, max_new_tokens=req.max_tokens or 2048,
            temperature=max(req.temperature, 0.01), do_sample=req.temperature > 0,
        )
        gen_ids = [o[len(i):] for i, o in zip(model_inputs.input_ids, gen_ids)]
        resp_text = tokenizer_ref.batch_decode(gen_ids, skip_special_tokens=True)[0]
        return {
            "id": request_id, "object": "chat.completion",
            "created": int(time.time()), "model": req.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": resp_text}, "finish_reason": "stop"}],
        }

if __name__ == "__main__":
    load_model()
    try:
        from pycloudflared import try_cloudflare
        tunnel = try_cloudflare(port=PORT)
        print("=" * 60)
        print(f"CODE68 TUNNEL URL: {tunnel.tunnel}/v1")
        print()
        print("On your LOCAL machine, set these in your .env file:")
        print(f"  CODE68_BASE_URL={tunnel.tunnel}/v1")
        print(f"  CODE68_API_KEY={API_KEY}")
        print("=" * 60)
    except Exception as e:
        print(f"Tunnel setup failed: {e}")
        print(f"Server available at http://localhost:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
"""


# ----- CELL 3: Paste this into the THIRD notebook cell -----

# !python /kaggle/working/code68_server.py
