import requests
import json
from pathlib import Path

SERVER = "http://WEB_SERVER_IP:5000"

def upload_mission(mission_dir):
    results_dir = Path(mission_dir) / "results"
    images_dir = Path(mission_dir) / "images"

    for json_file in results_dir.glob("*.json"):
        image_name = json_file.stem + ".jpg"
        image_path = images_dir / image_name

        # Upload JSON
        with open(json_file) as f:
            data = json.load(f)

        r = requests.post(f"{SERVER}/api/results", json=data, timeout=5)
        if r.status_code != 200:
            print("Failed JSON:", json_file)
            continue

        # Upload image
        with open(image_path, "rb") as img:
            files = {"image": img}
            r = requests.post(
                f"{SERVER}/api/images/{data['image_id']}",
                files=files,
                timeout=10
            )

        if r.status_code == 200:
            print("Uploaded:", json_file)
        else:
            print("Image failed:", image_name)
