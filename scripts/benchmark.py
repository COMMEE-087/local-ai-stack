#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark.py — local LLM speed + accuracy benchmark
Benchmark any OpenAI-compatible endpoint (e.g. llama-swap) for:
  - time-to-first-token (incl. model load)
  - prompt throughput (tok/s)
  - generation throughput (tok/s)
  - a fixed accuracy quiz

Usage:
  python benchmark.py [model...]            # default models listed below
  python benchmark.py --url http://HOST:PORT/v1/chat/completions qwen3:8b

All configuration is parametrized; nothing is hard-coded to a specific host.
Adjust MODEL_DEFAULTS to your own llama-swap model aliases.
"""
import json, sys, time, urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# --- config: parametrize for your environment -------------------------------
# Endpoint of your OpenAI-compatible server (llama-swap / llama.cpp / etc.)
URL = "http://localhost:PORT/v1/chat/completions"

# Default model aliases to bench when none are passed on the CLI.
MODEL_DEFAULTS = ["qwen3:8b", "qwen2.5:14b", "qwen3:30b"]

# --- accuracy quiz (fixed, unambiguous, easy to auto-check) -----------------
ACCURACY = [
    {"q": "Calculate: 17 × 23 = ? Output only the number.",
     "check": lambda s: "391" in s},
    {"q": "What is the capital of China? Output only the city name.",
     "check": lambda s: any(k in s for k in ["Beijing", "北京"])},
    {"q": "Sort the list [3,1,4,1,5,9,2,6] ascending, output only the sorted array.",
     "check": lambda s: "1, 1, 2, 3, 4, 5, 6, 9" in s or "[1, 1, 2, 3, 4, 5, 6, 9]" in s},
    {"q": "Explain in one sentence: what is RAG (retrieval-augmented generation)?",
     "check": lambda s: len(s) > 20},
    {"q": "Translate this sentence into English: 今天天气很好。 (Today the weather is nice.)",
     "check": lambda s: "weather" in s.lower() or "nice" in s.lower() or "good" in s.lower()},
]


def parse_args(argv):
    url = URL
    models = []
    i = 0
    while i < len(argv):
        if argv[i] == "--url" and i + 1 < len(argv):
            url = argv[i + 1]
            i += 2
        else:
            models.append(argv[i])
            i += 1
    return url, models or list(MODEL_DEFAULTS)


def call(url, model, prompt, max_tokens=200):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read().decode())
    ttfb_ms = (time.time() - t0) * 1000  # includes model load on first call
    msg = data["choices"][0]["message"]
    ch = (msg.get("content") or "") + (msg.get("reasoning_content") or "")
    tg = data.get("timings", {})
    return ch, ttfb_ms, tg


def main():
    url, models = parse_args(sys.argv[1:])
    print(f"Endpoint: {url}")
    for m in models:
        print(f"\n{'=' * 64}\n=== model: {m} ===")
        # throughput sample
        sample = ("The capital of China is Beijing, and Shanghai is the economic center. "
                  "Write a short Chinese paragraph about urban development, ~100 characters.")
        ch, ttfb, tg = call(url, m, sample)
        pps = tg.get("prompt_per_second", 0)
        gps = tg.get("predicted_per_second", 0)
        print(f"  time-to-first-token (incl. load): {ttfb / 1000:.1f}s")
        print(f"  prompt throughput: {pps:.1f} tok/s | generation: {gps:.1f} tok/s")
        # accuracy quiz
        score = 0
        for item in ACCURACY:
            try:
                a, _, _ = call(url, m, item["q"], max_tokens=300)
                ok = item["check"](a)
                score += ok
                print(f"    [{'OK' if ok else 'XX'}] {item['q'][:25]}... -> {a[:45]!r}")
            except Exception as e:
                print(f"    [!] {item['q'][:25]}... error: {e}")
        print(f"  == accuracy: {score}/{len(ACCURACY)}")


if __name__ == "__main__":
    main()
