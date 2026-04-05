import re

with open('src/zimage/cli.py', 'r') as f:
    content = f.read()

# I need to add load_config to the imports from paths
content = content.replace(
    """get_outputs_dir,
            get_loras_dir,
            get_db_path,""",
    """get_outputs_dir,
            get_loras_dir,
            get_db_path,
            load_config,"""
)
content = content.replace(
    """get_outputs_dir,
    get_loras_dir,
    get_db_path,""",
    """get_outputs_dir,
    get_loras_dir,
    get_db_path,
    load_config,"""
)

with open('src/zimage/cli.py', 'w') as f:
    f.write(content)
