import re

with open('src/zimage/cli.py', 'r') as f:
    content = f.read()

content = content.replace("get_db_path,\n                get_config_path,\n", "get_db_path,\n                get_config_path,\n                load_config,\n")
content = content.replace("get_db_path,\n            get_config_path,\n", "get_db_path,\n            get_config_path,\n            load_config,\n")
content = content.replace("get_db_path,\n        get_config_path,\n", "get_db_path,\n        get_config_path,\n        load_config,\n")

with open('src/zimage/cli.py', 'w') as f:
    f.write(content)
