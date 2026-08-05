---
name: localimg
description: Describe or analyze local image files with a local OpenAI-compatible vision LLM endpoint. Use when the user asks for local image explanation, image description, screenshot analysis, visual inspection, or wants to send an image file to the local vision model.
---

# Local Image Analysis

Use the bundled script to analyze local image files through the configured local vision endpoint. Prefer the script over rewriting the base64, JSON payload, curl, and response extraction flow.

## Usage

```bash
bash .caret/skills/localimg/scripts/describe_image.sh IMG_0084.jpg
bash .caret/skills/localimg/scripts/describe_image.sh screenshot.png "List visible UI issues."
MODEL=qwen3627b_code ENDPOINT=http://makkalot.local:8001/v1/chat/completions bash .caret/skills/localimg/scripts/describe_image.sh photo.jpeg
```

Defaults:

- `MODEL=qwen3627b_code`
- `ENDPOINT=http://makkalot.local:8001/v1/chat/completions`
- `AUTH_TOKEN=sk-no-key`
- `MAX_TIME=120`
- Prompt: `Describe this image in detail.`

Override `MODEL`, `ENDPOINT`, `AUTH_TOKEN`, or `MAX_TIME` with environment variables when needed.

## Notes

- Pass a readable local image path as the first argument.
- Pass a custom prompt as the second argument when the user asks for specific visual analysis.
- The script supports `jpg`, `jpeg`, `png`, `webp`, and `gif` MIME types by extension, defaulting to `image/jpeg`.
- Live calls require the local endpoint to be reachable. In sandboxed environments, request network permission if the call fails because network access is restricted.
