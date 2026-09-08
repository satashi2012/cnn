"""
CNN Indonesia Live Stream - Wowza Secure Token Generator
Replicates token generation logic from detikVideo.core.js
Designed to run on GitHub Actions
"""

import hashlib
import base64
import time
import urllib.parse
import json
import os
import re
import requests


# ============================================================
# Configuration extracted from detikVideo.core.js
# CNN Indonesia marker config
# ============================================================

CONFIG = {
    "stMarkerUrl": "live.cnnindonesia.com/livecnn/smil:cnntv.smil/playlist.m3u8",
    "stVideoUrl": "https://live.cnnindonesia.com/livecnn-sec/smil:cnntv.smil/playlist.m3u8",
    "stAutoFill": True,
    "stExpireInMinutes": 15,
    "stEnableEndTimeOnly": True,
    "stEnableStartTimeAndEndTime": False,
    "stDomain": "https://live.cnnindonesia.com",
    "stUrlPrefix": "livecnn-sec/smil:",
    "stUrlPostfix": "",
    "stUrlParams": "",
    "stShSc": "5da9533f4da8bd76",  # default shared secret for CNN
    "stPrefixParameter": "wowzatoken",
    "stStartTime": "",
    "stEndTime": "",
    "stAutoRefreshVideoUrl": True,
    "stForceRefreshBeforeExpire": 1,
}

# Shared secret values array (index 0-29)
ST_SHSC_VALUES = [
    "807aad1578ee7d9a", "258eed02421df5e2", "5da9533f4da8bd76",
    "a95951f3c250f6b2", "f3d2b8e1a0c45976", "71a9c3d5e8b240f1",
    "bc5029a7d31ef842", "4e81d6f0a2c5973b", "92f5b810d7e436ac",
    "1a3d6f8e2c5b0947", "d0e9a2f5c7b38164", "6c4b82d1f9e0a573",
    "3f1a0e7d5c92b846", "a5b8c1d4e7f02396", "8d2e5a1c9f0b7364",
    "27b4e9d1a8f5c036", "50c3f8a2d7b1e964", "e6d1b0c9f4a72583",
    "94a7d2e5b8c1f036", "1b8d5e2a9c6f0347", "f3a1b82d90c4e75b",
    "6d0e92f1a53b8c74", "2b5d8f40e91a63c7", "a7c2e5b9d0f48163",
    "1e8a3d6f2b9c5074", "94b0d1e7c5a2f836", "3f61b9d4a8e20c57",
    "c80d2f5a9e31b647", "51e9c3b8f0a7d426", "b2d5a8f13c9e6047",
]

# CShSc cookie values (index 0-29)
CSHSC_VALUES = [
    "3bcdb206", "a7f2d91b", "5e8c12a4", "bc394e0f", "d9b0f731",
    "82d1c5a9", "2a6e84bd", "f4b029e8", "9c1d5f27", "6d1a38f2",
    "0b4e92ac", "e5927c10", "73f5a1d8", "1c8d4b26", "f2e09b4c",
    "92a3f8d5", "4d8c1a2e", "3b6e07f1", "a5b2d7f0", "0f2a9d83",
    "d4e1a7b3", "2f8c0b59", "a1d6e942", "7b03f2c8", "59ac14de",
    "e2d73b0f", "84f196a5", "3c5d82e1", "0a9b4f76", "6d2e5b18",
]


def generate_wowza_token(config=None, cshsc_value_idx=1):
    """
    Generate Wowza secure token replicating detikVideo.core.js stMain() logic.

    The token generation follows these steps:
    1. Auto-fill: parse the video URL to extract stUrlPostfix
    2. Calculate startTime and endTime
    3. Build hash input: stUrlPrefix + stUrlPostfix + "?" + stShSc + "&" +
       stPrefixParameter + "endtime=" + endTime + "&" +
       stPrefixParameter + "starttime=" + startTime
    4. SHA256 hash -> Base64 -> URL-safe (replace + with -, / with _)
    5. Build final URL with token parameters

    Args:
        config: dict with CNN Indonesia stream config (uses default if None)
        cshsc_value_idx: index for the cshsc cookie value (default 1 from HTML)

    Returns:
        dict with 'url' (final m3u8 URL), 'cookie' (cshx cookie value),
        'expire_minutes', 'start_time', 'end_time'
    """
    if config is None:
        config = CONFIG.copy()

    video_url = config["stVideoUrl"]
    st_domain = config["stDomain"]
    st_url_prefix = config["stUrlPrefix"]
    st_prefix_param = config["stPrefixParameter"]
    st_sh_sc = config["stShSc"]
    expire_minutes = config["stExpireInMinutes"]

    # --- Step 1: Auto-fill stUrlPostfix ---
    # Parse: remove domain + "/" + stUrlPrefix from videoUrl, then remove "/playlist.m3u8"
    url_without_params = video_url.split("?")[0]
    st_url_params = ""
    if len(video_url.split("?")) > 1:
        st_url_params = video_url.split("?")[1]

    postfix_part = url_without_params.replace(st_domain + "/" + st_url_prefix, "")
    st_url_postfix = postfix_part.replace("/playlist.m3u8", "")

    # --- Step 2: Calculate times ---
    now_ms = int(time.time() * 1000)
    end_time_ms = now_ms + (expire_minutes * 60 * 1000)

    if config["stEnableStartTimeAndEndTime"]:
        # Both set to "0" (disabled)
        start_time = "0"
        end_time = "0"
    elif config["stEnableEndTimeOnly"]:
        # startTime = "0", endTime = calculated
        start_time = "0"
        end_time = str(end_time_ms)
    else:
        start_time = str(now_ms)
        end_time = str(end_time_ms)

    # --- Step 3: Build hash input ---
    # Format: stUrlPrefix + stUrlPostfix + "?" + stShSc + "&" +
    #         stPrefixParameter + "endtime=" + endTime + "&" +
    #         stPrefixParameter + "starttime=" + startTime
    hash_input = (
        f"{st_url_prefix}{st_url_postfix}"
        f"?{st_sh_sc}"
        f"&{st_prefix_param}endtime={end_time}"
        f"&{st_prefix_param}starttime={start_time}"
    )

    # --- Step 4: SHA256 hash -> Base64 -> URL-safe ---
    sha256_hash = hashlib.sha256(hash_input.encode("utf-8")).digest()
    hash_base64 = base64.b64encode(sha256_hash).decode("utf-8")

    # Make URL-safe: replace + with -, / with _
    hash_url_safe = hash_base64.replace("+", "-").replace("/", "_")

    # --- Step 5: Build final URL ---
    if st_url_params == "":
        url_suffix = (
            f"{st_prefix_param}starttime={start_time}"
            f"&{st_prefix_param}endtime={end_time}"
            f"&{st_prefix_param}hash={urllib.parse.quote(hash_url_safe, safe='')}"
        )
    else:
        url_suffix = (
            f"{st_prefix_param}starttime={start_time}"
            f"&{st_prefix_param}endtime={end_time}"
            f"&{st_prefix_param}hash={urllib.parse.quote(hash_url_safe, safe='')}"
            f"&{st_url_params}"
        )

    # Build the complete URL
    base_url = video_url.split("?")[0]
    final_url = f"{base_url}?{url_suffix}"

    # CShSc cookie value
    cshsc_cookie = CSHSC_VALUES[cshsc_value_idx]

    return {
        "url": final_url,
        "cookie_name": "cshx",
        "cookie_value": cshsc_cookie,
        "cookie_domain": ".cnnindonesia.com",
        "expire_minutes": expire_minutes,
        "start_time": start_time,
        "end_time": end_time,
        "hash_input": hash_input,
        "hash_base64": hash_base64,
        "hash_url_safe": hash_url_safe,
    }


def update_index_html(m3u8_url, html_path="index.html"):
    """Update index.html with the new tokenized m3u8 URL."""
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace the videoUrl in detikvideo_props
    pattern = r"(videoUrl\s*:\s*')[^']*(')"
    new_content = re.sub(pattern, rf"\g<1>{m3u8_url}\g<2>", content)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[OK] Updated {html_path} with new videoUrl")


def fetch_latest_js_config():
    """
    Fetch the latest detikVideo.core.js from CDN and extract
    the CNN Indonesia marker config + shared secrets.
    This ensures we always have the latest keys.
    """
    url = "https://cdn.detik.net.id/detikVideo/detikVideo.core.js"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0.0.0 Safari/537.36",
    }

    try:
        print("[INFO] Fetching latest detikVideo.core.js...")
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        js_content = resp.text

        # Extract stShScValues array
        shsc_match = re.search(
            r'stShScValues=\[([^\]]+)\]', js_content
        )
        if shsc_match:
            values_str = shsc_match.group(1)
            values = re.findall(r'"([^"]+)"', values_str)
            if values:
                global ST_SHSC_VALUES
                ST_SHSC_VALUES = values
                print(f"[OK] Extracted {len(values)} stShScValues")

        # Extract cshscValues array
        cshsc_match = re.search(
            r'cshscValues=\[([^\]]+)\]', js_content
        )
        if cshsc_match:
            values_str = cshsc_match.group(1)
            values = re.findall(r'"([^"]+)"', values_str)
            if values:
                global CSHSC_VALUES
                CSHSC_VALUES = values
                print(f"[OK] Extracted {len(values)} cshscValues")

        # Extract CNN Indonesia marker config
        cnn_marker_match = re.search(
            r'stMarkerUrl:"live\.cnnindonesia\.com/livecnn/smil:cnntv\.smil/playlist\.m3u8"'
            r'(.*?)stForceRefreshBeforeExpire:\d+\}',
            js_content
        )
        if cnn_marker_match:
            block = cnn_marker_match.group(0)
            # Extract stShSc for CNN
            shsc_m = re.search(r'stShSc:"([^"]+)"', block)
            if shsc_m:
                CONFIG["stShSc"] = shsc_m.group(1)
                print(f"[OK] CNN stShSc: {CONFIG['stShSc']}")

            # Extract stExpireInMinutes
            expire_m = re.search(r'stExpireInMinutes:(\d+)', block)
            if expire_m:
                CONFIG["stExpireInMinutes"] = int(expire_m.group(1))
                print(f"[OK] CNN stExpireInMinutes: {CONFIG['stExpireInMinutes']}")

            # Extract stVideoUrl
            vurl_m = re.search(r'stVideoUrl:"([^"]+)"', block)
            if vurl_m:
                CONFIG["stVideoUrl"] = vurl_m.group(1)
                print(f"[OK] CNN stVideoUrl: {CONFIG['stVideoUrl']}")

            # Extract stUrlPrefix
            prefix_m = re.search(r'stUrlPrefix:"([^"]+)"', block)
            if prefix_m:
                CONFIG["stUrlPrefix"] = prefix_m.group(1)
                print(f"[OK] CNN stUrlPrefix: {CONFIG['stUrlPrefix']}")

        return True

    except Exception as e:
        print(f"[WARN] Could not fetch latest JS config: {e}")
        print("[INFO] Using embedded fallback config")
        return False


def main():
    """Main entry point - generates token and updates index.html."""
    print("=" * 60)
    print("CNN Indonesia - Wowza Secure Token Generator")
    print("=" * 60)

    # Try to fetch latest config from CDN
    fetch_latest_js_config()

    # cshscValueIdx = 1 from the HTML config
    cshsc_idx = 1

    # Generate token
    result = generate_wowza_token(config=CONFIG, cshsc_value_idx=cshsc_idx)

    print()
    print(f"[TOKEN] Hash Input : {result['hash_input']}")
    print(f"[TOKEN] SHA256 B64 : {result['hash_base64']}")
    print(f"[TOKEN] URL-safe   : {result['hash_url_safe']}")
    print(f"[TOKEN] Start Time : {result['start_time']}")
    print(f"[TOKEN] End Time   : {result['end_time']}")
    print(f"[TOKEN] Expires    : {result['expire_minutes']} minutes")
    print(f"[TOKEN] Cookie     : {result['cookie_name']}={result['cookie_value']}")
    print()
    print(f"[URL] {result['url']}")
    print()

    # Update index.html
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    if os.path.exists(html_path):
        update_index_html(result["url"], html_path)
    else:
        print(f"[WARN] {html_path} not found, skipping HTML update")

    # Write result to JSON for GitHub Actions output
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[OK] Token result saved to {output_path}")

    # Set GitHub Actions output if running in CI
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"m3u8_url={result['url']}\n")
            f.write(f"cookie_value={result['cookie_value']}\n")
            f.write(f"expire_minutes={result['expire_minutes']}\n")
        print("[OK] GitHub Actions outputs set")


if __name__ == "__main__":
    main()
