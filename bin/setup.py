import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {"packages": ["argparse", "datetime", "os", "plistlib", "re", "sqlite3", "sys"]}

setup(  name = "ccextract",
        version = "1.0",
        description = "Extracts contacts from an iPod/iPhone backup and turns them into vCard format",
        options = {"build_exe": build_exe_options},
        executables = [Executable("ccextract.py")]
     )
