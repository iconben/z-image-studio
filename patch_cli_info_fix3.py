import re

with open('src/zimage/cli.py', 'r') as f:
    content = f.read()

old_str = """        f"  Outputs Dir: {info['paths']['outputs_dir']}",
        f"  LoRAs Dir: {info['paths']['loras_dir']}",
        f"  DB Path: {info['paths']['db_path']}",
        "",
        "Environment Overrides:"""

new_str = """        f"  Outputs Dir: {info['paths']['outputs_dir']}",
        f"  LoRAs Dir: {info['paths']['loras_dir']}",
        f"  DB Path: {info['paths']['db_path']}",
        "",
        "Constraints:",
        f"  Max Steps: {info['constraints']['max_steps']}",
        f"  Max Width: {info['constraints']['max_width']}",
        f"  Max Height: {info['constraints']['max_height']}",
        "",
        "Environment Overrides:"""

content = content.replace(old_str, new_str)

with open('src/zimage/cli.py', 'w') as f:
    f.write(content)
