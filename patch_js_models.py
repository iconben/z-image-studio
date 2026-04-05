with open('src/zimage/static/js/main.js', 'r') as f:
    content = f.read()

# 1. Remove the standalone loadConfig call
old_startup = """        // --- Config Limits Logic ---
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
        ]);"""

new_startup = """        console.log("Z-Image Studio: Running startup load...");
        await Promise.all([
            loadModels(),
            loadHistory()
        ]);"""

content = content.replace(old_startup, new_startup)

# 2. Add limits logic to loadModels
old_load_models = """        // --- Models Loading Logic ---
        async function loadModels() {
            try {
                const res = await fetch('/models');
                const data = await res.json();

                if (data.device) window.currentDevice = data.device;
                if (data.default_precision) window.defaultPrecision = data.default_precision;"""

new_load_models = """        // --- Models Loading Logic ---
        async function loadModels() {
            try {
                const res = await fetch('/models');
                const data = await res.json();

                if (data.constraints) {
                    const stepsEl = document.getElementById('steps');
                    if (stepsEl && data.constraints.max_steps) {
                        stepsEl.max = data.constraints.max_steps;
                    }

                    const widthEl = document.getElementById('width');
                    if (widthEl && data.constraints.max_width) {
                        widthEl.max = data.constraints.max_width;
                    }

                    const heightEl = document.getElementById('height');
                    if (heightEl && data.constraints.max_height) {
                        heightEl.max = data.constraints.max_height;
                    }
                }

                if (data.device) window.currentDevice = data.device;
                if (data.default_precision) window.defaultPrecision = data.default_precision;"""

content = content.replace(old_load_models, new_load_models)

with open('src/zimage/static/js/main.js', 'w') as f:
    f.write(content)
