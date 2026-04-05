with open('src/zimage/cli.py', 'r') as f:
    content = f.read()

# Let's see what collect_info returns currently
old_collect = """        "paths": {
            "module_file": str(Path(__file__).resolve()),
            "config_path": str(get_config_path().resolve()),
            "data_dir": str(get_data_dir().resolve()),
            "outputs_dir": str(get_outputs_dir().resolve()),
            "loras_dir": str(get_loras_dir().resolve()),
            "db_path": str(get_db_path().resolve()),
        },
        "env_overrides": {"""

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
        "env_overrides": {"""

if old_collect in content:
    content = content.replace(old_collect, new_collect)

with open('src/zimage/cli.py', 'w') as f:
    f.write(content)
