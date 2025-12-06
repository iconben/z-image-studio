(function () {
    const themeIconMap = {
        light: 'bi-sun-fill',
        dark: 'bi-moon-stars-fill',
        auto: 'bi-circle-half'
    };

    const getStoredTheme = () => localStorage.getItem('zimage_theme');
    const setStoredTheme = (theme) => localStorage.setItem('zimage_theme', theme);
    const getPreferredTheme = () => getStoredTheme() || 'auto';

    function initTheme(toggleButton) {
        if (!toggleButton) return;

        const setTheme = (theme) => {
            let actualTheme = theme;
            if (theme === 'auto') {
                actualTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            }
            document.documentElement.setAttribute('data-bs-theme', actualTheme);

            const iconClass = themeIconMap[theme] || 'bi-circle-half';
            const iconEl = toggleButton.querySelector('i');
            if (iconEl) {
                iconEl.className = `bi ${iconClass}`;
            }

            document.querySelectorAll('#themeToggleButton + .dropdown-menu .dropdown-item').forEach((item) => {
                if (item.getAttribute('data-theme-value') === theme) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });
        };

        setTheme(getPreferredTheme());

        document.querySelectorAll('#themeToggleButton + .dropdown-menu .dropdown-item').forEach((toggle) => {
            toggle.addEventListener('click', () => {
                const theme = toggle.getAttribute('data-theme-value');
                setStoredTheme(theme);
                setTheme(theme);
            });
        });

        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            const storedTheme = getStoredTheme();
            if (!storedTheme || storedTheme === 'auto') {
                setTheme('auto');
            }
        });

        return { setTheme };
    }

    window.themeSwitcher = { initTheme };
})();
