# -*- mode: python ; coding: utf-8 -*-
r"""
SuShe Build Script (main.spec)
==============================

This PyInstaller specification file builds the SuShe application with different options
based on command-line flags. It can:
1. Build the executable only (--exe)
2. Build the executable and signed installer (--installer)
3. Complete the build process and create a GitHub release (--release)

Usage:
------
IMPORTANT: You must use the -- separator before any custom build flags!

pyinstaller main.spec -- [build options]

Build Options:
  --exe       : Build executable only (default if no option specified)
  --installer : Build executable and create signed installer
  --release   : Build executable, installer, and create GitHub release

Examples:
---------
# Just build the executable (for testing)
pyinstaller main.spec -- --exe

# Build executable and create signed installer
pyinstaller main.spec -- --installer

# Complete build process with GitHub release
pyinstaller main.spec -- --release

# Default (no arguments) will build executable only
pyinstaller main.spec

Requirements:
------------
- PyInstaller
- Windows SDK (for signtool.exe)
- Inno Setup (for creating installer)
- GitHub CLI (for release mode only)
- Code signing certificate at C:\Users\meo\cert.pfx

Notes:
-----
- The script will prompt for the certificate password when needed
- For GitHub release, you'll be guided through the process interactively
- Version number is read from version.txt file
- The executable is signed in all modes
"""

import os
import subprocess
import glob
import sys
import argparse
from getpass import getpass

# Parse command-line arguments for build mode
# Print full sys.argv for debugging
print("\n=== DEBUG: COMMAND LINE ARGUMENTS ===")
print(f"Full sys.argv: {sys.argv}")
print(f"Length of sys.argv: {len(sys.argv)}")
for i, arg in enumerate(sys.argv):
    print(f"  sys.argv[{i}] = '{arg}'")
print("=====================================\n")

# Default values
build_level = 1  # Default: just build executable
build_mode = "--exe"  # Default display value

# Try to find our build flags
if len(sys.argv) > 1:
    # Check for --installer anywhere in the arguments
    if "--installer" in sys.argv:
        build_level = 2
        build_mode = "--installer"
        print("DEBUG: Found --installer flag directly in sys.argv")
    # Check for --release anywhere in the arguments
    elif "--release" in sys.argv:
        build_level = 3
        build_mode = "--release"
        print("DEBUG: Found --release flag directly in sys.argv")
    # Check for --exe anywhere in the arguments
    elif "--exe" in sys.argv:
        build_level = 1
        build_mode = "--exe"
        print("DEBUG: Found --exe flag directly in sys.argv")
    
    # Also try to find the -- separator
    try:
        separator_index = sys.argv.index("--")
        if separator_index < len(sys.argv) - 1:
            # Get all arguments after --
            args_after_separator = sys.argv[separator_index+1:]
            print(f"DEBUG: Arguments after -- separator: {args_after_separator}")
            
            # Check these arguments
            if "--installer" in args_after_separator:
                build_level = 2
                build_mode = "--installer"
                print("DEBUG: Found --installer flag after -- separator")
            elif "--release" in args_after_separator:
                build_level = 3
                build_mode = "--release"
                print("DEBUG: Found --release flag after -- separator")
            elif "--exe" in args_after_separator:
                build_level = 1
                build_mode = "--exe"
                print("DEBUG: Found --exe flag after -- separator")
    except ValueError:
        print("DEBUG: No -- separator found in command line arguments")

print(f"\n=== Build Mode ===")
print("Available modes:")
print("  --exe       : Build executable only")
print("  --installer : Build executable and installer")
print("  --release   : Build executable, installer, and GitHub release")
print(f"Selected mode: {build_mode} (build_level = {build_level})")
print("===============\n")

block_cipher = None

# Read version number from 'version.txt'
with open('version.txt', 'r') as f:
    version = f.read().strip()

# Define the output folder name, including the version number
output_name = f'SuShe_v{version}'

# Define additional data files and directories to be included
datas = [
    ('style.qss', '.'),
    ('settings_style.qss', '.'), 
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

# Always sign the executable regardless of build level
try:
    # Prompt the user for the password securely
    pfx_password = getpass("Enter the password for the signing certificate: ")

    # Path to the signed executable
    build_output_dir = os.path.abspath(os.path.join('dist', output_name))  # Use dist directory
    signed_exe_path = os.path.join(build_output_dir, "SuShe.exe")

    if not os.path.exists(signed_exe_path):
        raise FileNotFoundError(f"The expected executable was not found at {signed_exe_path}")

    # Find signtool.exe path - search for the correct version (x64 only)
    signtool_base_path = r"C:\Program Files (x86)\Windows Kits\10\bin"
    signtool_path = None
    
    # First try to find x64 version directly
    for root, dirs, files in os.walk(signtool_base_path):
        # Only look in directories that contain "x64" to ensure we get the x64 version
        if "x64" in os.path.basename(root) and "signtool.exe" in files:
            signtool_path = os.path.join(root, "signtool.exe")
            print(f"Found x64 signtool.exe at: {signtool_path}")
            break
    
    # If we couldn't find x64 version specifically, try a more targeted approach
    if not signtool_path:
        print("Searching for x64 signtool.exe using a different method...")
        # Look for version directories first (like 10.0.22621.0)
        for version_dir in os.listdir(signtool_base_path):
            version_path = os.path.join(signtool_base_path, version_dir)
            if os.path.isdir(version_path):
                # Now look specifically for the x64 directory
                x64_path = os.path.join(version_path, "x64")
                if os.path.isdir(x64_path):
                    signtool_x64 = os.path.join(x64_path, "signtool.exe")
                    if os.path.exists(signtool_x64):
                        signtool_path = signtool_x64
                        print(f"Found x64 signtool.exe at: {signtool_path}")
                        break
    
    if not signtool_path:
        raise FileNotFoundError("Could not find signtool.exe. Please check your Windows SDK installation.")

    # Certificate file path
    cert_path = r"C:\Users\meo\cert.pfx"
    
    if not os.path.exists(cert_path):
        raise FileNotFoundError(f"Certificate file not found at {cert_path}")

    # Command to sign the executable
    print("Signing the executable...")
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
    
    subprocess.run(sign_command, check=True)
    print(f"Successfully signed {signed_exe_path}")
    
    # Exit if level is 1 (executable only)
    if build_level == 1:
        print("\nBuild completed at Level 1: Executable only (signed)")
        print(f"The signed executable is available at: {signed_exe_path}")
        sys.exit(0)
    
    # Continue with installer creation for levels 2 and 3
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
    
    # Exit if level is 2 (executable and installer only)
    if build_level == 2:
        print("\nBuild completed at Level 2: Executable and installer (both signed)")
        print(f"The installer is available at: {installer_path}")
        sys.exit(0)
    
    # Level 3: Create GitHub release section with defaults
    print("\n==== GitHub Release ====")

    # Check if GitHub CLI is installed
    try:
        gh_version = subprocess.run(["gh", "--version"], capture_output=True, text=True, check=False)
        if gh_version.returncode != 0:
            print("GitHub CLI (gh) is not installed or not available in PATH.")
            print("You can install it with: winget install GitHub.cli")
            print("Skipping GitHub release creation.")
            sys.exit(1)
        
        print(f"GitHub CLI detected: {gh_version.stdout.splitlines()[0]}")
        
        # Create a git tag
        tag_name = f"v{version}"
        
        # Check if there are any changes to commit
        git_status = subprocess.run(
            ["git", "status", "--porcelain"], 
            capture_output=True, 
            text=True, 
            check=True
        ).stdout.strip()
        
        if git_status:
            print(f"Uncommitted changes detected:\n{git_status}")
            # Ask if user wants to commit changes (default: yes)
            commit_changes = input("Do you want to commit changes first? (y/n) [y]: ").strip().lower() or 'y'
            if commit_changes == 'y':
                commit_message = input("Enter commit message [Release version " + version + "]: ").strip()
                if not commit_message:
                    commit_message = f"Release version {version}"
                    
                subprocess.run(["git", "add", "."], check=True)
                subprocess.run(["git", "commit", "-m", commit_message], check=True)
                print("Changes committed.")
                
                # Push changes to remote
                print("Pushing changes to remote...")
                subprocess.run(["git", "push", "origin"], check=True)
                print("Changes pushed to remote.")
        else:
            print("No uncommitted changes detected. Skipping commit step.")
        
        # Create and push tag (default: yes)
        create_tag = input(f"Create and push tag '{tag_name}'? (y/n) [y]: ").strip().lower() or 'y'
        if create_tag == 'y':
            # Check if tag already exists
            tag_exists = subprocess.run(
                ["git", "tag", "-l", tag_name], 
                capture_output=True, 
                text=True, 
                check=True
            ).stdout.strip()
            
            if tag_exists:
                print(f"Tag {tag_name} already exists.")
                replace_tag = input("Replace existing tag? (y/n) [y]: ").strip().lower() or 'y'
                if replace_tag == 'y':
                    # Delete local and remote tag
                    subprocess.run(["git", "tag", "-d", tag_name], check=True)
                    try:
                        subprocess.run(["git", "push", "origin", f":{tag_name}"], check=True)
                    except subprocess.CalledProcessError:
                        print("Warning: Could not delete remote tag. It might not exist or you might not have permission.")
                    
                    # Create new tag
                    subprocess.run(["git", "tag", "-a", tag_name, "-m", f"Version {version}"], check=True)
                    subprocess.run(["git", "push", "origin", tag_name], check=True)
                    print(f"Tag {tag_name} created and pushed.")
                else:
                    print("Keeping existing tag.")
            else:
                # Create new tag
                subprocess.run(["git", "tag", "-a", tag_name, "-m", f"Version {version}"], check=True)
                subprocess.run(["git", "push", "origin", tag_name], check=True)
                print(f"Tag {tag_name} created and pushed.")
        
        # Create GitHub release (default: yes)
        create_github_release = input("Create GitHub release? (y/n) [y]: ").strip().lower() or 'y'
        if create_github_release == 'y':
            # Simplified release notes options
            notes_option = input("Release notes options:\n1. Generate automatically (default)\n2. Enter manually\nChoose option (1-2) [1]: ").strip() or '1'
            
            release_cmd = ["gh", "release", "create", tag_name, "--title", f"SuShe {tag_name}"]
            
            if notes_option == '1':
                release_cmd.append("--generate-notes")
            elif notes_option == '2':
                print("Enter release notes (end with a line containing only '###'):")
                notes_lines = []
                while True:
                    line = input()
                    if line == "###":
                        break
                    notes_lines.append(line)
                
                notes_content = "\n".join(notes_lines)
                # Create a temporary file for the notes
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as temp:
                    temp.write(notes_content)
                    temp_notes_path = temp.name
                
                release_cmd.extend(["--notes-file", temp_notes_path])
            else:
                print("Invalid option. Using auto-generated notes.")
                release_cmd.append("--generate-notes")
            
            # Add the installer file
            release_cmd.append(installer_path)
            
            # Create the release
            print("Creating GitHub release...")
            try:
                subprocess.run(release_cmd, check=True)
                print(f"GitHub release '{tag_name}' created successfully!")
            except subprocess.CalledProcessError as e:
                print(f"Error creating GitHub release: {e}")
            
            # Clean up temporary notes file if it was created
            if notes_option == '2' and 'temp_notes_path' in locals():
                try:
                    os.unlink(temp_notes_path)
                except:
                    pass

        print("\nBuild completed at Level 3: Executable, installer, and GitHub release")
        
    except Exception as e:
        print(f"Error with GitHub release process: {e}")
        sys.exit(1)

except Exception as e:
    print(f"Error in build process: {e}")
    sys.exit(1)