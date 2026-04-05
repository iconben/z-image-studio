import re

with open('src/zimage/cli.py', 'r') as f:
    content = f.read()

# Make sure constraints are actually output (I noticed they didn't show up in the output)
# Let's check where they should be inserted.
# Ah, I replaced "Environment Overrides:" with "Hardware:", I might have lost "Environment Overrides:".

with open('src/zimage/cli.py', 'w') as f:
    f.write(content)
