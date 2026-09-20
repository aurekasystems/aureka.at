"""Upload public/ using plain passive FTP. Never delete remote files."""
from ftplib import FTP, error_perm
import os
from pathlib import Path
import sys

PUBLIC = Path(__file__).resolve().parents[1] / "public"


def deploy():
    names = ("FTP_HOST", "FTP_USERNAME", "FTP_PASSWORD", "FTP_REMOTE_DIR")
    settings = {name: os.environ.get(name, "") for name in names}
    missing = [name for name, value in settings.items() if not value.strip()]
    if missing:
        raise ValueError("Missing GitHub secrets: " + ", ".join(missing))
    if any("\r" in value or "\n" in value for value in settings.values()):
        raise ValueError("FTP settings must not contain line breaks.")
    if "://" in settings["FTP_HOST"] or "/" in settings["FTP_HOST"]:
        raise ValueError("FTP_HOST must be a hostname, without protocol or path.")
    if ".." in settings["FTP_REMOTE_DIR"].split("/"):
        raise ValueError("FTP_REMOTE_DIR must not contain parent traversal.")
    paths = sorted(PUBLIC.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("Symlinks are not allowed in public/.")
    files = [path for path in paths if path.is_file()]
    if not (PUBLIC / "index.html").is_file():
        raise ValueError("public/index.html is required.")
    for path in paths:
        if any(part.startswith(".") for part in path.relative_to(PUBLIC).parts):
            raise ValueError("Hidden files or directories are not allowed in public/.")
        if "\r" in path.name or "\n" in path.name:
            raise ValueError("Invalid filename in public/.")

    # Deliberately FTP, not FTP_TLS: standard unencrypted FTP on port 21.
    with FTP(timeout=60) as ftp:
        ftp.connect(settings["FTP_HOST"], 21)
        ftp.login(settings["FTP_USERNAME"], settings["FTP_PASSWORD"])
        ftp.set_pasv(True)
        # Require an existing webroot; never guess or create the configured root.
        ftp.cwd(settings["FTP_REMOTE_DIR"])
        root = ftp.pwd()
        files.sort(key=lambda path: (path.name == "index.html", path.as_posix()))
        for path in files:
            relative = path.relative_to(PUBLIC)
            ftp.cwd(root)
            for part in relative.parts[:-1]:
                try:
                    ftp.cwd(part)
                except error_perm as error:
                    if not str(error).startswith("550"):
                        raise
                    ftp.mkd(part)
                    ftp.cwd(part)
            with path.open("rb") as source:
                ftp.storbinary("STOR " + path.name, source)
            print("Uploaded " + relative.as_posix())
    print(f"Done: {len(files)} files uploaded; no remote files deleted.")


if __name__ == "__main__":
    try:
        deploy()
    except Exception as error:
        # Server errors may echo credentials or secret paths; do not log them.
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        else:
            print(f"FTP deployment failed ({type(error).__name__}). Check credentials, existing remote directory and server availability.", file=sys.stderr)
        sys.exit(1)