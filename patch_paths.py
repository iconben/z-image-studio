import re

with open('src/zimage/paths.py', 'r') as f:
    content = f.read()

# Add max constraints to config default
old_config = """    config = {
        "version": 1,
        "Z_IMAGE_STUDIO_DATA_DIR": None,
        "Z_IMAGE_STUDIO_OUTPUT_DIR": None,
        "ZIMAGE_ENABLE_TORCH_COMPILE": None,
    }"""

new_config = """    config = {
        "version": 1,
        "Z_IMAGE_STUDIO_DATA_DIR": None,
        "Z_IMAGE_STUDIO_OUTPUT_DIR": None,
        "ZIMAGE_ENABLE_TORCH_COMPILE": None,
        "max_steps": 50,
        "max_width": 4096,
        "max_height": 4096,
    }"""

content = content.replace(old_config, new_config)

with open('src/zimage/paths.py', 'w') as f:
    f.write(content)
