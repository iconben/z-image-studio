import re

with open('tests/test_cli_info.py', 'r') as f:
    content = f.read()

old_paths = """            "paths": {
                "module_file": "a",
                "config_path": "b",
                "data_dir": "c",
                "outputs_dir": "d",
                "loras_dir": "e",
                "db_path": "f",
            },"""

new_paths = """            "paths": {
                "module_file": "a",
                "config_path": "b",
                "data_dir": "c",
                "outputs_dir": "d",
                "loras_dir": "e",
                "db_path": "f",
            },
            "constraints": {
                "max_steps": 50,
                "max_width": 4096,
                "max_height": 4096,
            },"""

content = content.replace(old_paths, new_paths)

with open('tests/test_cli_info.py', 'w') as f:
    f.write(content)
