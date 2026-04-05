import re

with open('src/zimage/cli.py', 'r') as f:
    content = f.read()

# 1. Update collect_info
old_collect = """        "paths": {
            "module_file": str(Path(__file__).resolve()),
            "config_path": str(get_config_path().resolve()),
            "data_dir": str(get_data_dir().resolve()),
            "outputs_dir": str(get_outputs_dir().resolve()),
            "loras_dir": str(get_loras_dir().resolve()),
            "db_path": str(get_db_path().resolve()),
        },
        "hardware": hardware,
    }"""

new_collect = """        "paths": {
            "module_file": str(Path(__file__).resolve()),
            "config_path": str(get_config_path().resolve()),
            "data_dir": str(get_data_dir().resolve()),
            "outputs_dir": str(get_outputs_dir().resolve()),
            "loras_dir": str(get_loras_dir().resolve()),
            "db_path": str(get_db_path().resolve()),
        },
        "constraints": {
            "max_steps": load_config().get("max_steps", 50),
            "max_width": load_config().get("max_width", 4096),
            "max_height": load_config().get("max_height", 4096),
        },
        "hardware": hardware,
    }"""
content = content.replace(old_collect, new_collect)


# 2. Update format_info_text
old_format = """        f"  Outputs Dir: {info['paths']['outputs_dir']}",
        f"  LoRAs Dir: {info['paths']['loras_dir']}",
        f"  DB Path: {info['paths']['db_path']}",
        "",
        "Hardware:"
    ]"""

new_format = """        f"  Outputs Dir: {info['paths']['outputs_dir']}",
        f"  LoRAs Dir: {info['paths']['loras_dir']}",
        f"  DB Path: {info['paths']['db_path']}",
        "",
        "Constraints:",
        f"  Max Steps: {info['constraints']['max_steps']}",
        f"  Max Width: {info['constraints']['max_width']}",
        f"  Max Height: {info['constraints']['max_height']}",
        "",
        "Hardware:"
    ]"""
content = content.replace(old_format, new_format)

with open('src/zimage/cli.py', 'w') as f:
    f.write(content)
