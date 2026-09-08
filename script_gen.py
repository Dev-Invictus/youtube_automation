"""
script_gen.py (FREE VERSION - no API key needed)

Instead of calling the Anthropic API, this reads a JSON script from a local
file that YOU fill in manually:

1. Open prompt_template.txt, replace TOPIC_GOES_HERE with your topic
2. Paste the whole thing into free Claude.ai chat (or ChatGPT free tier)
3. Copy the JSON reply it gives you
4. Paste it into script_input.json in this folder (replacing the placeholder)
5. Run main.py as normal - it reads from script_input.json automatically
"""
import json
import os

SCRIPT_INPUT_PATH = "script_input.json"


def generate_script(topic: str, target_seconds: int = 60) -> dict:
    if not os.path.exists(SCRIPT_INPUT_PATH):
        raise FileNotFoundError(
            f"\n\n{SCRIPT_INPUT_PATH} not found.\n"
            f"1. Open prompt_template.txt and swap in your topic: {topic}\n"
            f"2. Paste it into free Claude.ai or ChatGPT chat\n"
            f"3. Copy the JSON reply into a new file called {SCRIPT_INPUT_PATH}\n"
            f"4. Re-run this script.\n"
        )

    with open(SCRIPT_INPUT_PATH, "r") as f:
        data = json.load(f)

    return {
        "title": data["title"],
        "script": data["narration"],
        "captions": data["captions"],
    }


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "3 surprising facts about Docker"
    result = generate_script(topic)
    print(result["title"])
    print("---")
    print(result["script"])
