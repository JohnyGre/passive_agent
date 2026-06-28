
import httpx
import os
from pathlib import Path

# Load .env file
BASE_DIR = Path(__file__).parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

# --- Configuration ---
GUMROAD_API = "https://api.gumroad.com/v2"
ACCESS_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN")

def check_gumroad_login():
    """
    Checks if the Gumroad access token is valid by fetching user data.
    """
    if not ACCESS_TOKEN:
        print("❌ ERROR: GUMROAD_ACCESS_TOKEN not found in environment/.env file.")
        return

    print(f"🔑 Verifying Gumroad Access Token...")

    try:
        with httpx.Client() as client:
            res = client.get(
                f"{GUMROAD_API}/user",
                params={"access_token": ACCESS_TOKEN}
            )

            print(f"Request URL: {res.url}")
            print(f"Response Status Code: {res.status_code}")

            if res.status_code == 200:
                user_data = res.json()
                if user_data.get("success"):
                    user = user_data.get("user", {})
                    print("✅ SUCCESS: Authentication successful!")
                    print(f"   - User ID: {user.get('id')}")
                    print(f"   - Email: {user.get('email')}")
                    print(f"   - Name: {user.get('name')}")
                else:
                    print(f"⚠️ WARNING: Request succeeded but operation failed.")
                    print(f"   - Response: {res.text}")

            else:
                print(f"❌ ERROR: Authentication failed.")
                try:
                    # Try to print JSON error if available
                    print(f"   - Response: {res.json()}")
                except Exception:
                    # Fallback to raw text
                    print(f"   - Response: {res.text}")
            
            res.raise_for_status()

    except httpx.HTTPStatusError as e:
        print(f"
HTTP Error details: {e.response.text}")
    except httpx.RequestError as e:
        print(f"
Request error occurred: {e}")
    except Exception as e:
        print(f"
An unexpected error occurred: {e}")

if __name__ == "__main__":
    # Inject truststore if available, as in the original config
    try:
        import truststore
        truststore.inject_into_ssl()
        print("🔒 truststore injected for SSL verification.")
    except ImportError:
        print("⚠️ truststore not found, using default SSL context.")
        pass
    check_gumroad_login()
