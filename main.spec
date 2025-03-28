# -*- mode: python ; coding: utf-8 -*-

import os
import subprocess
import glob
from getpass import getpass

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

# Signing the executable (custom step)
try:
    # Prompt the user for the password securely
    pfx_password = getpass("Enter the password for the signing certificate: ")

    # Path to the signed executable
    build_output_dir = os.path.abspath(os.path.join('dist', output_name))  # Use dist directory
    signed_exe_path = os.path.join(build_output_dir, "SuShe.exe")

    if not os.path.exists(signed_exe_path):
        raise FileNotFoundError(f"The expected executable was not found at {signed_exe_path}")

    # Path to signtool.exe
    signtool_path = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"

    # Command to sign the executable
    sign_command = [
        signtool_path,
        "sign",
        "/f", r"C:\Users\meo\cert.pfx",          # Path to your .pfx file
        "/p", pfx_password,                         # Password entered by the user
        "/tr", "http://timestamp.digicert.com",     # Timestamp server
        "/td", "sha256",                            # Timestamp digest algorithm
        "/fd", "sha256",                            # File digest algorithm
        signed_exe_path                             # Path to the .exe file
    ]

    # Run the signing command
    subprocess.run(sign_command, check=True)
    print(f"Successfully signed {signed_exe_path}")

except Exception as e:
    print(f"Error signing the executable: {e}")