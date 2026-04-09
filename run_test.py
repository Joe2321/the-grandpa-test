#!/usr/bin/env python3
"""
The Grandpa Test — LLM Cross-Layer Reasoning Benchmark
Run the ant-and-grasshopper story test against multiple LLM providers.

Usage:
    python run_test.py --model gpt-5          # Test a single model
    python run_test.py --provider openai       # Test all models from a provider
    python run_test.py --all                   # Test all models
    python run_test.py --list                  # List available models

Environment variables:
    OPENAI_API_KEY      - OpenAI API key
    ANTHROPIC_API_KEY   - Anthropic API key
    GOOGLE_API_KEY      - Google AI API key
    XAI_API_KEY         - xAI (Grok) API key
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPT_FILE = SCRIPT_DIR / "prompt.txt"
OUTPUT_DIR = SCRIPT_DIR / "results" / "raw"

MODELS = [
    # OpenAI
    {"name": "GPT-5",          "id": "gpt-5",              "provider": "openai"},
    {"name": "GPT-4o",         "id": "gpt-4o",             "provider": "openai"},
    {"name": "GPT-4.1-mini",   "id": "gpt-4.1-mini",       "provider": "openai"},
    {"name": "GPT-4.1-nano",   "id": "gpt-4.1-nano",       "provider": "openai"},
    {"name": "o3",             "id": "o3",                  "provider": "openai"},
    {"name": "o3-mini",        "id": "o3-mini",             "provider": "openai"},
    {"name": "o4-mini",        "id": "o4-mini",             "provider": "openai"},
    # Anthropic
    {"name": "Claude Opus 4",    "id": "claude-opus-4-20250514",     "provider": "anthropic"},
    {"name": "Claude Sonnet 4",  "id": "claude-sonnet-4-20250514",   "provider": "anthropic"},
    {"name": "Claude Haiku 3.5", "id": "claude-3-5-haiku-20241022",  "provider": "anthropic"},
    # Google
    {"name": "Gemini 3.1 Pro",   "id": "gemini-3.1-pro",            "provider": "google"},
    {"name": "Gemini 2.5 Pro",   "id": "gemini-2.5-pro-preview-05-06", "provider": "google"},
    {"name": "Gemini 3 Flash",   "id": "gemini-3-flash",            "provider": "google"},
    {"name": "Gemini 2.5 Flash", "id": "gemini-2.5-flash-preview-04-17", "provider": "google"},
    {"name": "Gemini 2.0 Flash", "id": "gemini-2.0-flash",          "provider": "google"},
    {"name": "Gemma 4 31B",     "id": "gemma-4-31b-it",             "provider": "google"},
    {"name": "Gemma 3 27B",     "id": "gemma-3-27b-it",             "provider": "google"},
    # xAI
    {"name": "Grok-4",        "id": "grok-4",                "provider": "xai"},
    {"name": "Grok-4-fast",   "id": "grok-4-fast-reasoning", "provider": "xai"},
    {"name": "Grok-3",        "id": "grok-3",                "provider": "xai"},
    {"name": "Grok-3-mini",   "id": "grok-3-mini",           "provider": "xai"},
]

# ---------------------------------------------------------------------------
# API callers
# ---------------------------------------------------------------------------

def _openai_chat(model_id: str, prompt: str, api_key: str) -> str:
    """Call OpenAI-compatible chat completions."""
    import requests
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
    }
    # o-series models don't support temperature
    if not model_id.startswith("o"):
        body["temperature"] = 0.3
    resp = requests.post(url, headers=headers, json=body, timeout=300)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _anthropic_chat(model_id: str, prompt: str, api_key: str) -> str:
    """Call Anthropic Messages API."""
    import requests
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": model_id,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    return "".join(block["text"] for block in data["content"] if block["type"] == "text")


def _google_chat(model_id: str, prompt: str, api_key: str) -> str:
    """Call Google Generative AI REST API."""
    import requests
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_id}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3},
    }
    resp = requests.post(url, json=body, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _xai_chat(model_id: str, prompt: str, api_key: str) -> str:
    """Call xAI (Grok) chat completions (OpenAI-compatible)."""
    import requests
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=300)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


PROVIDER_CALLERS = {
    "openai": ("OPENAI_API_KEY", _openai_chat),
    "anthropic": ("ANTHROPIC_API_KEY", _anthropic_chat),
    "google": ("GOOGLE_API_KEY", _google_chat),
    "xai": ("XAI_API_KEY", _xai_chat),
}

# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def run_single(model_info: dict, prompt: str) -> dict:
    """Run the test on a single model and return the result dict."""
    name = model_info["name"]
    model_id = model_info["id"]
    provider = model_info["provider"]

    env_var, caller = PROVIDER_CALLERS[provider]
    api_key = os.environ.get(env_var, "")
    if not api_key:
        print(f"  ⏭  Skipping {name} — {env_var} not set")
        return None

    print(f"\n{'='*60}")
    print(f"  Testing: {name} ({model_id})")
    print(f"{'='*60}")

    start = time.time()
    error = None
    response = ""
    try:
        response = caller(model_id, prompt, api_key)
        elapsed = time.time() - start
        preview = response[:200] + "..." if len(response) > 200 else response
        print(f"  ✅ Done in {elapsed:.1f}s")
        print(f"  {preview}")
    except Exception as exc:
        elapsed = time.time() - start
        error = str(exc)
        response = f"ERROR: {error}"
        print(f"  ❌ Error in {elapsed:.1f}s: {error}")

    result = {
        "model_name": name,
        "model_id": model_id,
        "provider": provider,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "response": response,
    }
    if error:
        result["error"] = error

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = name.replace(" ", "-").replace("/", "_")

    json_path = OUTPUT_DIR / f"{safe_name}.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    txt_path = OUTPUT_DIR / f"{safe_name}.txt"
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write(f"Model: {name} ({model_id})\n")
        fh.write(f"Provider: {provider}\n")
        fh.write(f"Time: {elapsed:.1f}s\n")
        fh.write(f"Date: {result['timestamp']}\n")
        fh.write(f"{'='*60}\n\n")
        fh.write(response)

    print(f"  💾 Saved to {json_path.name}")
    return result


def find_model(query: str) -> list[dict]:
    """Find models matching a query string (case-insensitive, partial match)."""
    q = query.lower().strip()
    return [m for m in MODELS if q in m["name"].lower() or q in m["id"].lower()]


def list_models():
    """Print all available models."""
    print(f"\n{'='*60}")
    print("  Available Models")
    print(f"{'='*60}\n")
    current_provider = None
    for m in MODELS:
        if m["provider"] != current_provider:
            current_provider = m["provider"]
            env_var = PROVIDER_CALLERS[current_provider][0]
            has_key = "✅" if os.environ.get(env_var) else "❌"
            print(f"\n  [{current_provider.upper()}] ({env_var} {has_key})")
        print(f"    {m['name']:25s}  {m['id']}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="The Grandpa Test — LLM Cross-Layer Reasoning Benchmark"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--model", "-m", help="Test a specific model (partial name match)")
    group.add_argument("--provider", "-p", help="Test all models from a provider")
    group.add_argument("--all", "-a", action="store_true", help="Test all models")
    group.add_argument("--list", "-l", action="store_true", help="List available models")
    parser.add_argument("--delay", "-d", type=float, default=1.0,
                        help="Delay between requests in seconds (default: 1.0)")
    args = parser.parse_args()

    if args.list:
        list_models()
        return

    # Load prompt
    if not PROMPT_FILE.exists():
        print(f"❌ Prompt file not found: {PROMPT_FILE}")
        sys.exit(1)
    prompt = PROMPT_FILE.read_text(encoding="utf-8")

    # Determine which models to test
    if args.model:
        targets = find_model(args.model)
        if not targets:
            print(f"❌ No model matching '{args.model}'. Use --list to see available models.")
            sys.exit(1)
    elif args.provider:
        prov = args.provider.lower()
        targets = [m for m in MODELS if m["provider"] == prov]
        if not targets:
            print(f"❌ Unknown provider '{args.provider}'. Available: openai, anthropic, google, xai")
            sys.exit(1)
    else:  # --all
        targets = MODELS

    print(f"\n🐜 The Grandpa Test — Testing {len(targets)} model(s)\n")

    results = []
    for i, model in enumerate(targets):
        result = run_single(model, prompt)
        if result:
            results.append(result)
        if i < len(targets) - 1:
            time.sleep(args.delay)

    # Summary
    print(f"\n\n{'='*60}")
    print(f"  Complete! Tested {len(results)}/{len(targets)} models.")
    print(f"  Results saved to: {OUTPUT_DIR}/")
    print(f"{'='*60}\n")

    if results:
        print("  Model                      Time")
        print("  " + "-" * 40)
        for r in results:
            status = "❌ ERR" if r.get("error") else "✅"
            print(f"  {status} {r['model_name']:24s} {r['elapsed_seconds']:6.1f}s")


if __name__ == "__main__":
    main()
