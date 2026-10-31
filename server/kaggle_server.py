"""Kaggle Cloud Inference Server for Code68.

Runs Qwen2.5-Coder-7B-Instruct (4-bit quantized) on 2x NVIDIA Tesla T4 GPUs
and exposes a secure, authenticated OpenAI-compatible API.
Supports automatic local fallback mode when running on non-GPU machines for testing.
"""

import os
import json
import time
import uuid
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Configuration from environment variables
API_KEY = os.getenv("CODE68_API_KEY", "code68-secret-key")
MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen2.5-Coder-7B-Instruct")
HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", 8000))

app = FastAPI(title="Code68 Cloud LLM Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication dependency
def verify_api_key(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization Header Format")
    if parts[1] != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")
    return parts[1]


# Data schemas matching OpenAI Chat Completions API
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


# Model globals
model = None
tokenizer = None
is_mock_mode = False


def load_model():
    global model, tokenizer, is_mock_mode
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        if not torch.cuda.is_available():
            print("[INFO] No NVIDIA GPU detected. Switching to local mock/developer mode.")
            is_mock_mode = True
            return

        print(f"Loading {MODEL_ID} in 4-bit on available GPUs...")
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )

        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
            torch_dtype=torch.float16,
            trust_remote_code=True,
        )
        print("[INFO] Model loaded successfully onto GPU!")
    except ImportError as e:
        print(f"[INFO] PyTorch/Transformers not installed ({e}). Running in local mock/developer mode.")
        is_mock_mode = True
    except Exception as e:
        print(f"[WARNING] Error loading model: {e}. Falling back to local mock mode.")
        is_mock_mode = True


@app.get("/health")
def health():
    gpu_avail = False
    try:
        import torch
        gpu_avail = torch.cuda.is_available()
    except Exception:
        pass
    return {
        "status": "ok",
        "gpu_available": gpu_avail,
        "model": MODEL_ID,
        "mode": "gpu_inference" if (model is not None and not is_mock_mode) else "mock_developer_mode",
    }


@app.get("/v1/models")
def list_models(auth: str = Depends(verify_api_key)):
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "code68",
            }
        ]
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, auth: str = Depends(verify_api_key)):
    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # 1. Mock developer mode (when testing locally without GPU)
    if is_mock_mode or model is None:
        last_user_msg = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
        mock_response = (
            f"[Local Mock Inference Server] Successfully received request.\n\n"
            f"Your instruction was: '{last_user_msg}'\n\n"
            f"When deployed on Kaggle with 2x NVIDIA Tesla T4 GPUs, this server streams outputs directly "
            f"from '{MODEL_ID}' (4-bit quantized)."
        )

        if req.stream:
            async def mock_stream_generator():
                words = mock_response.split(" ")
                for i, word in enumerate(words):
                    chunk_text = word + (" " if i < len(words) - 1 else "")
                    chunk = {
                        "id": request_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": req.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": chunk_text},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                    await asyncio.sleep(0.04)

                end_chunk = {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(end_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(mock_stream_generator(), media_type="text/event-stream")
        else:
            return {
                "id": request_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": mock_response},
                        "finish_reason": "stop",
                    }
                ],
            }

    # 2. Real GPU Model Inference
    import torch

    hf_messages = []
    for m in req.messages:
        d = {"role": m.role, "content": m.content or ""}
        if m.name:
            d["name"] = m.name
        if m.tool_call_id:
            d["tool_call_id"] = m.tool_call_id
        if m.tool_calls:
            d["tool_calls"] = m.tool_calls
        hf_messages.append(d)

    try:
        if req.tools and hasattr(tokenizer, "apply_chat_template"):
            text = tokenizer.apply_chat_template(
                hf_messages,
                tools=req.tools,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            text = tokenizer.apply_chat_template(
                hf_messages,
                tokenize=False,
                add_generation_prompt=True,
            )
    except Exception:
        text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in hf_messages) + "\nASSISTANT: "

    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    if req.stream:
        async def event_generator():
            from transformers import TextIteratorStreamer
            from threading import Thread

            streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=False)
            generation_kwargs = dict(
                model_inputs,
                streamer=streamer,
                max_new_tokens=req.max_tokens or 2048,
                temperature=req.temperature,
                do_sample=req.temperature > 0,
            )

            thread = Thread(target=model.generate, kwargs=generation_kwargs)
            thread.start()

            for new_text in streamer:
                chunk = {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": req.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": new_text},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.001)

            end_chunk = {
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": req.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(end_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    else:
        generated_ids = model.generate(
            **model_inputs,
            max_new_tokens=req.max_tokens or 2048,
            temperature=req.temperature,
            do_sample=req.temperature > 0,
        )
        generated_ids = [
            output_ids[len(input_ids):]
            for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        response_text = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

        return {
            "id": request_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop",
                }
            ],
        }


if __name__ == "__main__":
    load_model()

    print("=" * 60)
    print("CODE68 CLOUD INFERENCE SERVER")
    print(f"Listening on: http://localhost:{PORT}")
    print(f"API Key: {API_KEY}")
    print(f"Model: {MODEL_ID}")
    print(f"Mode: {'GPU Inference (2x T4)' if (model is not None and not is_mock_mode) else 'Developer Mode (Local)'}")
    print("=" * 60)

    # Optionally launch cloudflare tunnel if pycloudflared installed
    try:
        from pycloudflared import try_cloudflare
        tunnel_url = try_cloudflare(port=PORT).tunnel
        print("=" * 60)
        print(f"PUBLIC TUNNEL URL: {tunnel_url}/v1")
        print(f"Set this in your local terminal:")
        print(f"export CODE68_BASE_URL={tunnel_url}/v1")
        print(f"export CODE68_API_KEY={API_KEY}")
        print("=" * 60)
    except Exception:
        pass

    uvicorn.run(app, host=HOST, port=PORT)
