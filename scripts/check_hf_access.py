import os
import sys
import urllib.error
import urllib.request


DEFAULT_MODEL_ID = "ZhengPeng7/BiRefNet"
MODEL_ID = os.environ.get("PIXAL3D_REMBG_MODEL") or DEFAULT_MODEL_ID
CHECK_URL = f"https://huggingface.co/{MODEL_ID}/resolve/main/config.json"
ACCESS_URL = f"https://huggingface.co/{MODEL_ID}"
TOKEN_URL = "https://huggingface.co/settings/tokens"


def fail(message: str, code: int = 1) -> None:
    print("")
    print("[Pixal3D] Hugging Face access check failed.")
    print(message)
    print("")
    print(f"[Pixal3D] Checked model: {MODEL_ID}")
    if MODEL_ID != DEFAULT_MODEL_ID:
        print(f"[Pixal3D] Open {ACCESS_URL} and make sure access is accepted for your account.")
        print(f"[Pixal3D] Then create or paste a read token from {TOKEN_URL} as HF_TOKEN in Pinokio.")
        print("[Pixal3D] If Pinokio autofills an old token, replace it from the app's Configure tab.")
    sys.exit(code)


def main() -> None:
    if os.environ.get("PIXAL3D_SKIP_HF_ACCESS_CHECK") == "1":
        print("[Pixal3D] Skipping Hugging Face access check.")
        return

    token = None
    if MODEL_ID != DEFAULT_MODEL_ID:
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = urllib.request.Request(CHECK_URL, method="HEAD", headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if 200 <= response.status < 400:
                print(f"[Pixal3D] Background-removal model access check passed for {MODEL_ID}.")
                return
            fail(f"Unexpected Hugging Face response status: {response.status}", 43)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            if token:
                fail(
                    f"The configured HF_TOKEN cannot access {MODEL_ID} yet. Hugging Face returned HTTP {exc.code}.",
                    44,
                )
            fail(f"{MODEL_ID} requires Hugging Face authentication. Hugging Face returned HTTP {exc.code}.", 42)
        fail(f"Hugging Face returned HTTP {exc.code} while checking {MODEL_ID}.", 45)
    except Exception as exc:
        fail(f"Could not check Hugging Face access for {MODEL_ID}: {exc}", 46)


if __name__ == "__main__":
    main()
