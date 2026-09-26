import os
import platform
import subprocess
import sys
import venv

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT, ".venv")

if platform.system() == "Windows":
    PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")
else:
    PYTHON = os.path.join(VENV_DIR, "bin", "python")


def main():
    print("Setting up ASCII Profile Generator...")
    print()

    if not os.path.exists(PYTHON):
        print("Creating virtual environment...")
        venv.create(VENV_DIR, with_pip=True)

    print("Installing required packages...")
    subprocess.check_call([
        PYTHON,
        "-m",
        "pip",
        "install",
        "-r",
        os.path.join(ROOT, "requirements.txt"),
    ])

    print()
    print("Setup complete.")
    print("Run: python ascii_generator.py my-photo.png")

if __name__ == "__main__":
    main()
