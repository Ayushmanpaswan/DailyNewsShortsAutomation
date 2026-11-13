from pathlib import Path
import os
import stat
import tempfile

from google_auth_oauthlib.flow import InstalledAppFlow


BASE_DIR = Path(__file__).resolve().parent
CLIENT_SECRET = BASE_DIR / "client_secret.json"
TOKEN_FILE = BASE_DIR / "token.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def save_token(token_json: str) -> None:
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=BASE_DIR,
            prefix=".token-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(token_json)

        try:
            os.chmod(temporary_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

        os.replace(temporary_path, TOKEN_FILE)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> None:
    if not CLIENT_SECRET.exists():
        raise FileNotFoundError(
            "client_secret.json was not found in the project directory."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET),
        SCOPES,
    )

    credentials = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )

    if not credentials.refresh_token:
        raise RuntimeError(
            "Google did not return a refresh token. "
            "Run authorization again and approve offline access."
        )

    save_token(credentials.to_json())

    print("YouTube OAuth authorization completed.")
    print("A fresh token.json containing a refresh token was saved locally.")
    print("No YouTube upload was performed.")


if __name__ == "__main__":
    main()
