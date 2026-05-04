#!/usr/bin/env python3
import os
import sys
import json
import py_compile
import re
from pathlib import Path

def get_files(root_dir, extension, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = []
    
    matched_files = []
    for root, dirs, files in os.walk(root_dir):
        # exclude directories
        dirs[:] = [d for d in dirs if not any(os.path.join(root, d).startswith(os.path.join(root_dir, excl)) for excl in exclude_dirs)]
        
        for file in files:
            if file.endswith(extension):
                matched_files.append(os.path.join(root, file))
    return matched_files

def check_python_syntax():
    print("Running Python syntax check...")
    python_files = get_files(".", ".py", exclude_dirs=["demos", "venv", ".opencode/node_modules"])
    errors = 0
    for f in python_files:
        try:
            py_compile.compile(f, doraise=True)
        except py_compile.PyCompileError as e:
            print(f"❌ Syntax error in {f}: {e}")
            errors += 1
    
    if errors == 0:
        print("✅ Python syntax check passed.\n")
    return errors == 0

def check_json_configs():
    print("Running JSON config check...")
    json_files = get_files("configs/vendor", ".json")
    errors = 0
    for f in json_files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                json.load(file)
        except json.JSONDecodeError as e:
            print(f"❌ JSON format error in {f}: {e}")
            errors += 1
        except Exception as e:
            print(f"❌ Could not read {f}: {e}")
            errors += 1

    if errors == 0:
        print("✅ JSON config check passed.\n")
    return errors == 0

def check_secrets():
    print("Running Secret scan...")
    # Check if .env is committed
    import subprocess
    try:
        result = subprocess.run(["git", "ls-files", ".env"], capture_output=True, text=True)
        if result.stdout.strip() == ".env":
            print("❌ Found .env file tracked by git! This should not be committed.")
            return False
    except Exception:
        pass

    extensions_to_check = [".py", ".json", ".md", ".ts", ".yml", ".yaml"]
    exclude_dirs = ["demos", "venv", ".opencode/node_modules", ".git"]
    
    files_to_check = []
    for ext in extensions_to_check:
        files_to_check.extend(get_files(".", ext, exclude_dirs=exclude_dirs))

    secret_patterns = [
        re.compile(r"(?:API_KEY|SECRET|TOKEN|PASSWORD)\s*(?:=|:)\s*['\"](?P<value>[a-zA-Z0-9_\-]{10,})['\"]", re.IGNORECASE),
        re.compile(r"sk-[a-zA-Z0-9]{32,}"),
        re.compile(r"AKID[a-zA-Z0-9]{32}")
    ]

    allowed_placeholders = ["your_key", "your_api_key", "example", "xxx", "YOUR_KEY", "your_secret", "sk-" + "12345678901234567890123456789012"]

    errors = 0
    for f in files_to_check:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                content = file.read()
                
                for pattern in secret_patterns:
                    for match in pattern.finditer(content):
                        # Extract the captured value if group 'value' exists, else use the whole match
                        val = match.group('value') if 'value' in match.groupdict() else match.group(0)
                        
                        # Check if it's an allowed placeholder
                        is_placeholder = any(placeholder in val.lower() for placeholder in allowed_placeholders) or val in allowed_placeholders
                        
                        if not is_placeholder:
                            print(f"❌ Potential secret found in {f}!")
                            # Do not print the secret itself!
                            errors += 1
        except Exception:
            pass # skip binary or unreadable files

    if errors == 0:
        print("✅ Secret scan passed.\n")
    return errors == 0

def check_markdown_links():
    print("Running Markdown link check...")
    errors = 0
    readme_path = Path("README.md")
    if not readme_path.exists():
        print("❌ README.md not found!")
        return False
        
    content = readme_path.read_text(encoding='utf-8')
    
    # regex to find markdown links: [text](./path) or [text](path)
    link_pattern = re.compile(r'\[.*?\]\((?!http)(.*?)\)')
    for match in link_pattern.finditer(content):
        link_path = match.group(1).split('#')[0] # remove anchor
        if not link_path:
            continue
            
        target = (readme_path.parent / link_path).resolve()
        if not target.exists():
            print(f"❌ Broken link in README.md: {link_path}")
            errors += 1
            
    if errors == 0:
        print("✅ Markdown link check passed.\n")
    return errors == 0

def main():
    success = True
    success &= check_python_syntax()
    success &= check_json_configs()
    success &= check_secrets()
    success &= check_markdown_links()
    
    if not success:
        print("❌ CI checks failed!")
        sys.exit(1)
    else:
        print("🚀 All CI checks passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()
