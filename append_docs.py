import os

soniox_rt_path = "/Volumes/work/OpenCode/VoiceAgent/.opencode/skills/vendor-soniox/soniox-docs/realtime-streaming.md"
soniox_batch_path = "/Volumes/work/OpenCode/VoiceAgent/.opencode/skills/vendor-soniox/soniox-docs/batch-prerecorded.md"
speechmatics_rt_path = "/Volumes/work/OpenCode/VoiceAgent/.opencode/skills/vendor-speechmatics/speechmatics-docs/realtime-streaming.md"

import urllib.request

def fetch_and_append(url, file_path, title):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')
            
            # Since these are HTML pages, we'll just write a link to them for now if we can't get raw markdown.
            # But wait, we can just append a placeholder if we don't have the raw markdown easily accessible in a script.
    except Exception as e:
        pass

# Instead of fetching, we'll just read the files and append a section header. 
# We'll use the LLM to write the actual content via edit tool next.
