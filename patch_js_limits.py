with open('src/zimage/static/js/main.js', 'r') as f:
    content = f.read()

# Let's insert a call to /info at startup and update DOM inputs
old_init = """    // Initialize components
    document.addEventListener("DOMContentLoaded", () => {
        // Initialize tooltips
        const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

        loadModels();"""

new_init = """    // Initialize components
    document.addEventListener("DOMContentLoaded", async () => {
        // Initialize tooltips
        const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

        // Load config limits
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

        loadModels();"""

content = content.replace(old_init, new_init)

with open('src/zimage/static/js/main.js', 'w') as f:
    f.write(content)
