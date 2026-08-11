#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ocr_demo.py — PaddleOCR one-shot document OCR (generic, no business data)

Shows the reusable skeleton worth keeping: per-line reading-order sorting and
table (CSV) grouping from raw OCR output. Adapt the file collection / output
paths to your own needs.

Pipeline: OCR a PDF/image -> extract (text, score, polygon) -> sort in
reading order -> group rows for a CSV-style table.

Depends on: paddleocr, pymupdf (for single-page PDF rendering)
"""
import sys, os, json, time, glob
sys.stdout.reconfigure(encoding="utf-8")

IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def load_ocr(model="PP-OCRv8_det", lang="en"):
    from paddleocr import PaddleOCR
    return PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        lang=lang,
        text_detection_model_name=model + "_det",
        text_recognition_model_name=model + "_rec",
    )


def extract_page(page_obj):
    """Extract (text, score, polygon) list from one OCRResult page."""
    res = page_obj.json["res"] if hasattr(page_obj, "json") else page_obj
    texts, scores, polys = res.get("rec_texts", []), res.get("rec_scores", []), res.get("rec_polys", [])
    items = []
    for i, t in enumerate(texts or []):
        items.append({
            "text": t,
            "score": float(scores[i]) if i < len(scores or []) else 0.0,
            "poly": polys[i] if i < len(polys or []) else None,
        })
    return items


def sort_reading_order(items):
    """Sort top-to-bottom; cluster into lines by center-y, then left-to-right by x."""
    if not items:
        return items
    for it in items:
        p = it["poly"]
        if p and len(p) >= 4:
            it["_cy"] = sum(pt[1] for pt in p) / len(p)
            it["_cx"] = sum(pt[0] for pt in p) / len(p)
        else:
            it["_cy"] = it["_cx"] = 0.0

    items.sort(key=lambda r: r["_cy"])
    heights = [max(pt[1] for pt in r["poly"]) - min(pt[1] for pt in r["poly"])
               for r in items if r["poly"] and len(r["poly"]) >= 4]
    avg_h = (sum(heights) / len(heights)) if heights else 20.0
    tol = avg_h * 0.6

    lines, cur, cur_y = [], [items[0]], items[0]["_cy"]
    for r in items[1:]:
        if abs(r["_cy"] - cur_y) <= tol:
            cur.append(r)
        else:
            lines.append(cur)
            cur, cur_y = [r], r["_cy"]
    lines.append(cur)

    result = []
    for line in lines:
        line.sort(key=lambda r: r["_cx"])
        for r in line:
            r.pop("_cy", None)
            r.pop("_cx", None)
            result.append(r)
    return result


def group_rows(items, y_tol=15):
    """Approximate table grouping: cluster by baseline-y, one CSV row per line."""
    ordered = sort_reading_order(items)
    rows, cur, cur_y = [], [], None
    for it in ordered:
        p = it["poly"]
        cy = (p[0][1] + p[2][1]) / 2 if p and len(p) >= 4 else 0.0
        if cur_y is None:
            cur_y = cy
        if abs(cy - cur_y) < y_tol:
            cur.append(it)
        else:
            if cur:
                rows.append(cur)
            cur, cur_y = [it], cy
    if cur:
        rows.append(cur)
    out = []
    for line in rows:
        line.sort(key=lambda x: x["poly"][0][0] if x["poly"] else 0)
        out.append([it["text"] for it in line])
    return out


def ocr_file(ocr, path, page=None):
    """OCR one file; returns {pages: [{items, rows, time_s}]}."""
    t0 = time.time()
    if page is not None and path.lower().endswith(".pdf"):
        import pymupdf
        doc = pymupdf.open(path)
        page = max(1, min(page, doc.page_count))
        pix = doc[page - 1].get_pixmap(dpi=200)
        tmp = os.path.join(os.path.dirname(path), "_tmp_page.png")
        pix.save(tmp)
        doc.close()
        results = ocr.predict(tmp)
        os.remove(tmp)
    else:
        results = ocr.predict(path)
    dt = time.time() - t0
    pages = []
    for i, page_obj in enumerate(results):
        items = sort_reading_order(extract_page(page_obj))
        pages.append({
            "page": i + 1,
            "items": items,
            "rows": group_rows(items),
            "time_s": round(dt / max(len(results), 1), 1),
        })
    return pages


def main():
    import argparse
    ap = argparse.ArgumentParser(description="PaddleOCR one-shot OCR (generic)")
    ap.add_argument("input", help="PDF/image file or directory")
    ap.add_argument("--out", default=None, help="output directory (default: input's dir)")
    ap.add_argument("--page", type=int, default=None, help="process only PDF page N")
    ap.add_argument("--model", default="PP-OCRv8_det", help="model name")
    ap.add_argument("--lang", default="en", help="language code")
    args = ap.parse_args()

    if os.path.isdir(args.input):
        files = []
        for ext in [".pdf"] + sorted(IMG_EXTS):
            files.extend(glob.glob(os.path.join(args.input, "**", "*" + ext), recursive=True))
        files = sorted(files)
    else:
        files = [args.input]
    if not files:
        print("no files found")
        sys.exit(1)

    print(f"initializing PaddleOCR ({args.model}, {args.lang})...", flush=True)
    ocr = load_ocr(args.model, args.lang)
    total_t0 = time.time()
    for i, f in enumerate(files):
        base = os.path.splitext(os.path.basename(f))[0]
        out_dir = args.out or os.path.dirname(f)
        print(f"[{i+1}/{len(files)}] {os.path.basename(f)} ...", flush=True)
        try:
            pages = ocr_file(ocr, f, args.page)
            with open(os.path.join(out_dir, base + "_ocr.json"), "w", encoding="utf-8") as fh:
                json.dump({"pages": pages}, fh, ensure_ascii=False, indent=2)
            with open(os.path.join(out_dir, base + "_ocr.txt"), "w", encoding="utf-8") as fh:
                for p in pages:
                    for it in p["items"]:
                        fh.write(it["text"] + "\n")
            print(f"  ok: {len(pages)} page(s), total {time.time()-total_t0:.1f}s")
        except Exception as e:
            print(f"  failed: {e}")
    print(f"done in {time.time()-total_t0:.1f}s")


if __name__ == "__main__":
    main()
