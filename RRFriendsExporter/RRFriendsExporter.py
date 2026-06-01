import argparse
import json
import os
import sys
from urllib import error, parse, request


def request_json(url, headers=None):
    req = request.Request(url, headers=headers or {}, method="GET")
    with request.urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        content = resp.read().decode(charset)
    return json.loads(content)


def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def download_image(image_name, destination_path):
    image_name = str(image_name).lstrip("/")
    image_url = f"https://img.rec.net/{image_name}"
    with request.urlopen(image_url, timeout=30) as resp:
        image_data = resp.read()
    with open(destination_path, "wb") as f:
        f.write(image_data)


def main():
    print("=== RRFriendsExporter ===\n")

    parser = argparse.ArgumentParser(description="RRFriendsExporter")
    parser.add_argument("--token", help="Bearer token for authentication")
    parser.add_argument("--json", dest="json_file", help="Path to the JSON file")
    args = parser.parse_args()

    if args.token:
        bearer_token = args.token.strip()
    else:
        print("Enter your Bearer token: ", end="", flush=True)
        bearer_token = sys.stdin.readline().strip()
    if not bearer_token:
        print("ERROR: Bearer token cannot be empty.")
        sys.exit(1)

    if args.json_file:
        json_file_path = args.json_file.strip().strip('"')
    else:
        json_file_path = input("Enter the path to the JSON file: ").strip().strip('"')
    if not os.path.isfile(json_file_path):
        print(f"ERROR: File not found: {json_file_path}")
        sys.exit(1)

    with open(json_file_path, "r", encoding="utf-8") as f:
        try:
            room_list = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to parse JSON file: {e}")
            sys.exit(1)

    if not isinstance(room_list, list):
        print("ERROR: JSON file must contain a top-level array [].")
        sys.exit(1)

    auth_headers = {"Authorization": f"Bearer {bearer_token}"}

    output_root = os.path.dirname(os.path.abspath(json_file_path))

    for index, item in enumerate(room_list, start=1):
        if not isinstance(item, dict):
            print(f"[{index}] Skipping non-object item.")
            continue

        player_id = item.get("PlayerID")
        if player_id is None:
            print(f"[{index}] Skipping object without PlayerID.")
            continue

        player_id_str = str(player_id).strip()
        if not player_id_str:
            print(f"[{index}] Skipping object with empty PlayerID.")
            continue

        player_folder = os.path.join(output_root, player_id_str)
        os.makedirs(player_folder, exist_ok=True)
        print(f"[{index}] Processing PlayerID: {player_id_str}")

        bulk_url = f"https://accounts.rec.net/account/bulk?id={parse.quote(player_id_str)}"
        try:
            bulk_json = request_json(bulk_url, headers=auth_headers)
        except error.HTTPError as e:
            print(f"[{index}] ERROR bulk request failed ({e.code}): {e.reason}")
            continue
        except error.URLError as e:
            print(f"[{index}] ERROR bulk request failed: {e.reason}")
            continue
        except json.JSONDecodeError as e:
            print(f"[{index}] ERROR parsing bulk JSON: {e}")
            continue

        bulk_json_path = os.path.join(player_folder, "bulk.json")
        save_json(bulk_json_path, bulk_json)

        account_obj = None
        if isinstance(bulk_json, list) and bulk_json and isinstance(bulk_json[0], dict):
            account_obj = bulk_json[0]

        if account_obj is None:
            print(f"[{index}] WARNING bulk JSON did not contain a single account object in an array.")
        else:
            for image_key in ("profileImage", "bannerImage"):
                image_value = account_obj.get(image_key)
                if not image_value:
                    print(f"[{index}] WARNING missing {image_key}.")
                    continue

                image_ext = os.path.splitext(str(image_value))[1] or ".img"
                image_filename = f"{image_key}{image_ext}"
                image_path = os.path.join(player_folder, image_filename)
                try:
                    download_image(image_value, image_path)
                except error.HTTPError as e:
                    print(f"[{index}] ERROR downloading {image_key} ({e.code}): {e.reason}")
                except error.URLError as e:
                    print(f"[{index}] ERROR downloading {image_key}: {e.reason}")

        bio_url = f"https://accounts.rec.net/account/{parse.quote(player_id_str)}/bio"
        try:
            bio_json = request_json(bio_url, headers=auth_headers)
            bio_json_path = os.path.join(player_folder, "bio.json")
            save_json(bio_json_path, bio_json)
        except error.HTTPError as e:
            print(f"[{index}] ERROR bio request failed ({e.code}): {e.reason}")
        except error.URLError as e:
            print(f"[{index}] ERROR bio request failed: {e.reason}")
        except json.JSONDecodeError as e:
            print(f"[{index}] ERROR parsing bio JSON: {e}")

    print("\nDone.")

if __name__ == "__main__":
    main()
