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

# Signing the executable and creating the installer
try:
    # Prompt the user for the password securely
    pfx_password = getpass("Enter the password for the signing certificate: ")

    # Path to the signed executable
    build_output_dir = os.path.abspath(os.path.join('dist', output_name))  # Use dist directory
    signed_exe_path = os.path.join(build_output_dir, "SuShe.exe")

    if not os.path.exists(signed_exe_path):
        raise FileNotFoundError(f"The expected executable was not found at {signed_exe_path}")

    # Find signtool.exe path - search for the correct version
    signtool_base_path = r"C:\Program Files (x86)\Windows Kits\10\bin"
    signtool_path = None
    
    # Try to find signtool.exe by searching through all versions
    for root, dirs, files in os.walk(signtool_base_path):
        if "signtool.exe" in files:
            signtool_path = os.path.join(root, "signtool.exe")
            print(f"Found signtool.exe at: {signtool_path}")
            break
    
    if not signtool_path:
        raise FileNotFoundError("Could not find signtool.exe. Please check your Windows SDK installation.")

    # Certificate file path
    cert_path = r"C:\Users\meo\cert.pfx"
    
    if not os.path.exists(cert_path):
        raise FileNotFoundError(f"Certificate file not found at {cert_path}")

    # Command to sign the executable
    sign_command = [
        signtool_path,
        "sign",
        "/f", cert_path,                             # Path to your .pfx file
        "/p", pfx_password,                          # Password entered by the user
        "/tr", "http://timestamp.digicert.com",      # Timestamp server
        "/td", "sha256",                             # Timestamp digest algorithm
        "/fd", "sha256",                             # File digest algorithm
        signed_exe_path                              # Path to the .exe file
    ]

    # Run the signing command
    print("Signing the executable...")
    subprocess.run(sign_command, check=True)
    print(f"Successfully signed {signed_exe_path}")

    # Find Inno Setup Compiler
    inno_setup_path = None
    possible_inno_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe"
    ]
    
    for path in possible_inno_paths:
        if os.path.exists(path):
            inno_setup_path = path
            print(f"Found Inno Setup at: {inno_setup_path}")
            break
    
    if not inno_setup_path:
        raise FileNotFoundError("Could not find Inno Setup. Please check your installation.")

    # Run Inno Setup to create the installer
    print("Creating installer with Inno Setup...")
    inno_command = [
        inno_setup_path,
        "SuSheInstaller.iss"
    ]
    
    subprocess.run(inno_command, check=True)
    print("Installer created successfully.")
    
    # Find the created installer file
    installer_dir = os.path.abspath("installer")
    installer_pattern = os.path.join(installer_dir, f"SuShe Installer v{version}*.exe")
    installer_files = glob.glob(installer_pattern)
    
    if not installer_files:
        raise FileNotFoundError(f"Could not find installer file matching pattern: {installer_pattern}")
    
    installer_path = installer_files[0]
    print(f"Found installer at: {installer_path}")
    
    # Sign the installer
    print("Signing the installer...")
    installer_sign_command = [
        signtool_path,
        "sign",
        "/f", cert_path,                            # Path to your .pfx file
        "/p", pfx_password,                         # Password entered by the user
        "/tr", "http://timestamp.digicert.com",     # Timestamp server
        "/td", "sha256",                            # Timestamp digest algorithm
        "/fd", "sha256",                            # File digest algorithm
        installer_path                              # Path to the installer .exe file
    ]
    
    subprocess.run(installer_sign_command, check=True)
    print(f"Successfully signed installer: {installer_path}")
    
    print("Build and signing process completed successfully!")

except Exception as e:
    print(f"Error in build process: {e}")