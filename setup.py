from setuptools import setup, find_packages

setup(
    name="velqimobile",
    version="1.0.0",
    description="Velqi Mobile - Music search and player",
    author="SalvAmigos",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "flet>=0.25.0",
        "yt-dlp>=2024.11.11",
        "requests>=2.31.0",
    ],
    extras_require={
        "desktop": [
            "pygame>=2.5.2",
            "imageio-ffmpeg>=0.4.9",
        ],
    },
    python_requires=">=3.8",
)