from setuptools import setup, find_packages

setup(
    name="yt_playlist_downloader_gui",
    version="1.0.0",
    description="A GUI desktop app (PyQt5 + yt-dlp) for downloading YouTube playlists and videos.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Tanmoy Giri",
    author_email="tanmoygiri333@gmail.com",
    url="https://github.com/iamtgiri/YT-Playlist-Downloader",
    license="GPLv3",
    packages=find_packages(exclude=("tests",)),
    include_package_data=True,
    install_requires=[
        "PyQt5>=5.15",
        "yt-dlp>=2025.8.27",
    ],
    entry_points={
        "gui_scripts": [
            "yt-downloader=app.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Topic :: Multimedia :: Video :: Download",
    ],
    python_requires=">=3.8",
)
