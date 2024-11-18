# -*- mode: python ; coding: utf-8 -*-

import os
import subprocess
import glob

block_cipher = None

# Read version number from 'version.txt'
with open('version.txt', 'r') as f:
    version = f.read().strip()

# Define the output folder name, including the version number
output_name = f'SuShe_v{version}'

# Define additional data files and directories to be included
datas = [
    ('style.qss', '.'),
    ('countries.txt', '.'),
    ('genres.txt', '.'),
    ('help.md', '.'),
    ('points.json', '.'),
    ('logos', 'logos'),
    ('config.json', '.'),
    ('version.txt', '.'),
]

# List of hidden imports that PyInstaller might miss
hiddenimports = [
#    'tempfile',           # Added because it's imported inside a function
#    'requests',           # Keep if PyInstaller misses it
#    'PIL',                # Keep if PyInstaller misses it
]

# Analysis configuration
a = Analysis(
    ['main.py'],
    pathex=['./'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Creating the PYZ archive
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Creating the executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SuShe',  # Name of the executable file
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True if you want to see the console output
    icon='logos/logo.ico'  # Path to your icon file
)

# Collecting all files
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=output_name,  # Use the versioned output folder name
)
