import re

content = open(r"D:\Schleiden\Obsidian\XDF\TEST\reference\XDF\Current Class\9999\9999 Lesson 1\9999 Lesson 1.md", encoding="utf-8").read()

# Test 1: exact ## (not ### or ####)
raw_match = re.search(r"### 原始记录\s*\n(.*?)(?=^## |^### [^#]|$)", content, re.DOTALL | re.MULTILINE)
if raw_match:
    rc = raw_match.group(1).strip()
    lines = [l for l in rc.split("\n") if l.strip() and not l.startswith("#")]
    print(f"Test1 matched {len(lines)} lines:")
    for l in lines:
        print(f"  {l[:60]}...")
else:
    print("Test1: No match!")

# Test 2: simpler approach - just count non-heading lines after 原始记录
pos = content.find("### 原始记录")
if pos >= 0:
    section = content[pos:]
    # Find next heading at same or higher level
    next_section = re.search(r"\n### [^#]|\n## ", section[20:])
    if next_section:
        rc = section[20:20+next_section.start()].strip()
    else:
        rc = section[20:].strip()
    lines = [l for l in rc.split("\n") if l.strip() and not l.startswith("#")]
    print(f"\nTest2 matched {len(lines)} lines:")
    for l in lines:
        print(f"  {l[:60]}...")
