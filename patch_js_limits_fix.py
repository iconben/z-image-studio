import re

with open('src/zimage/static/js/main.js', 'r') as f:
    content = f.read()

old_startup = """        console.log("Z-Image Studio: Running startup load...");
        await Promise.all([
            loadModels(),
            loadHistory()
        ]);
        renderActiveLoras(); """

new_startup = """        // --- Config Limits Logic ---
        async function loadConfig() {
            try {
                const res = await fetch('/info');
                if (res.ok) {
                    const info = await res.json();
                    if (info.constraints) {
                        const stepsEl = document.getElementById('steps');
                        if (stepsEl && info.constraints.max_steps) {
                            stepsEl.max = info.constraints.max_steps;
                        }

                        const widthEl = document.getElementById('width');
                        if (widthEl && info.constraints.max_width) {
                            widthEl.max = info.constraints.max_width;
                        }

                        const heightEl = document.getElementById('height');
                        if (heightEl && info.constraints.max_height) {
                            heightEl.max = info.constraints.max_height;
                        }
                    }
                }
            } catch (e) {
                console.error("Failed to load constraints:", e);
            }
        }

        console.log("Z-Image Studio: Running startup load...");
        await Promise.all([
            loadConfig(),
            loadModels(),
            loadHistory()
        ]);
        renderActiveLoras(); """

content = content.replace(old_startup, new_startup)

with open('src/zimage/static/js/main.js', 'w') as f:
    f.write(content)
