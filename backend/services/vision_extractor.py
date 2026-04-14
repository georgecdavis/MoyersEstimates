import base64
import json
import logging
import time
from pathlib import Path

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, VISION_BATCH_SIZE

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are an expert insurance estimate parser for Moyer's Services Group, a professional repair contractor.

Your job is to extract every line item from insurance repair estimate PDFs (Xactimate, Symbility, and custom carrier formats) and return structured JSON.

## Trade Categories
Assign exactly one trade from this list to each line item based on its description:
Demo, Drywall/Plaster, Electrician, Flooring-Carpet, Flooring-Tile, Flooring-Wood, HVAC, Windows, Doors, Cabinetry, Plumbing, Painting, Masonry/Fireplace, Cleaning, Temp/General Conditions, Moyers, Misc

## Trade Assignment Rules
- Demo: any demolition, removal, tear-out
- Drywall/Plaster: drywall, sheetrock, plaster, blueboard, tape, mud, texture
- Electrician: electrical, wiring, outlets, panels, fixtures, smoke detectors
- Flooring-Carpet: carpet, pad, carpet installation
- Flooring-Tile: ceramic, porcelain, tile, grout, mortar
- Flooring-Wood: hardwood, LVP, laminate, vinyl plank, wood floor
- HVAC: heating, cooling, ductwork, furnace, AC, air handler, vents
- Windows: windows, screens, window trim
- Doors: doors, door frames, door hardware, entry
- Cabinetry: cabinets, vanities, countertops, shelving
- Plumbing: pipes, fixtures, toilets, sinks, faucets, water heater
- Painting: paint, primer, caulk, stain, wallpaper
- Masonry/Fireplace: brick, block, mortar, fireplace, chimney, concrete
- Cleaning: cleaning, deodorizing, sanitizing, contents manipulation
- Temp/General Conditions: temporary toilet, dumpster, scaffolding, protection, permits, fees, taxes, project management, general labor
- Moyers: items that represent general contractor overhead, project supervision, or Moyer's-specific services that don't fit other categories
- Misc: anything that genuinely doesn't fit above

## JSON Output Format
Return ONLY valid JSON with no markdown, no explanation, no code fences. Use this exact schema:

{
  "metadata": {
    "insured_name": "Last, First or Full Name",
    "claim_number": "...",
    "insurance_company": "...",
    "property_address": "full address string",
    "loss_type": "Fire / Water / Wind / etc.",
    "date_of_loss": "MM/DD/YYYY or empty string"
  },
  "line_items": [
    {
      "section": "Section or Room name from the estimate",
      "description": "Full item description",
      "qty": 1.0,
      "unit": "EA",
      "unit_price": 0.00,
      "tax": 0.00,
      "o_and_p": 0.00,
      "rcv": 0.00,
      "depreciation": 0.00,
      "acv": 0.00,
      "trade": "Demo"
    }
  ]
}

## Critical Rules
- Extract EVERY numbered line item. Do not skip any.
- If a field is not shown for a line item, use 0.0 for numbers and "" for strings.
- Negative numbers are valid (depreciation is often shown in parentheses — convert to negative float).
- Descriptions may be cut off at page boundaries — include whatever text is visible.
- Section headers (like "General Conditions", "Kitchen", "Living Room") apply to all items below them until the next section header.
- Do NOT include section totals, subtotals, or summary rows — only individual line items.
- For metadata: only extract from the cover/header page. If no metadata is visible, return empty strings.
- If this is not the first batch of pages, metadata fields may already be known — return empty strings for metadata and focus on line_items only.
"""


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def _parse_response(text: str) -> dict:
    text = text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    # First try: parse as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Recovery: response was truncated mid-JSON.
    # Find the last complete line item (last '}' before the truncation)
    # and close the array + object properly.
    try:
        # Find the last complete object in the line_items array
        last_complete = text.rfind('},\n')
        if last_complete == -1:
            last_complete = text.rfind('}')
        if last_complete > 0:
            truncated = text[:last_complete + 1]
            # Close the line_items array and the outer object
            recovered = truncated.rstrip().rstrip(',') + '\n  ]\n}'
            return json.loads(recovered)
    except (json.JSONDecodeError, Exception):
        pass

    # If all recovery fails, re-raise with the original text for logging
    return json.loads(text)  # This will raise JSONDecodeError with the original error


def _call_vision(page_paths: list[str], is_first_batch: bool, retries: int = 3) -> dict:
    content = []

    if is_first_batch:
        content.append({
            "type": "text",
            "text": (
                "Extract all metadata and every line item from these estimate pages. "
                "Return ONLY the JSON object described in your instructions."
            )
        })
    else:
        content.append({
            "type": "text",
            "text": (
                "Extract every line item visible on these pages. Return empty strings for all metadata fields. "
                "Return ONLY the JSON object described in your instructions."
            )
        })

    for path in page_paths:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": _encode_image(path),
            }
        })

    for attempt in range(retries):
        raw_parts: list[str] = []
        try:
            with client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=64000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
            ) as stream:
                for delta in stream.text_stream:
                    raw_parts.append(delta)
                final = stream.get_final_message()
                if final.stop_reason == "max_tokens":
                    logger.warning(
                        "Claude hit max_tokens on attempt %d; truncation recovery will run",
                        attempt + 1,
                    )
            return _parse_response("".join(raw_parts))
        except json.JSONDecodeError as e:
            logger.warning("JSON parse error on attempt %d: %s", attempt + 1, e)
            if attempt == retries - 1:
                raise
        except anthropic.RateLimitError:
            wait = 20 * (attempt + 1)
            logger.warning("Rate limited, waiting %ds (attempt %d)", wait, attempt + 1)
            time.sleep(wait)
        except (anthropic.APIConnectionError, anthropic.APIError) as e:
            # Stream may have been cut mid-flight; try to salvage what we got
            # before falling through to retry.
            if raw_parts:
                try:
                    logger.warning(
                        "Stream interrupted on attempt %d (%s); attempting partial parse",
                        attempt + 1, e,
                    )
                    return _parse_response("".join(raw_parts))
                except json.JSONDecodeError:
                    pass
            logger.error("API error on attempt %d: %s", attempt + 1, e)
            if attempt == retries - 1:
                raise
            time.sleep(5)

    return {"metadata": {}, "line_items": []}


def extract_from_pages(
    page_paths: list[str],
    progress_callback=None
) -> tuple[dict, list[dict]]:
    """
    Process all rasterized pages in batches.
    Returns (metadata_dict, list_of_line_items).
    progress_callback(current_page, total_pages) called after each batch.
    """
    total = len(page_paths)
    batches = [
        page_paths[i: i + VISION_BATCH_SIZE]
        for i in range(0, total, VISION_BATCH_SIZE)
    ]

    metadata = {
        "insured_name": "",
        "claim_number": "",
        "insurance_company": "",
        "property_address": "",
        "loss_type": "",
        "date_of_loss": "",
    }
    all_items = []

    for batch_idx, batch in enumerate(batches):
        is_first = batch_idx == 0
        logger.info("Processing batch %d/%d (%d pages)", batch_idx + 1, len(batches), len(batch))

        result = _call_vision(batch, is_first_batch=is_first)

        if is_first and result.get("metadata"):
            for k, v in result["metadata"].items():
                if v and k in metadata:
                    metadata[k] = v

        items = result.get("line_items", [])
        all_items.extend(items)

        if progress_callback:
            pages_done = min((batch_idx + 1) * VISION_BATCH_SIZE, total)
            progress_callback(pages_done, total)

    return metadata, all_items
