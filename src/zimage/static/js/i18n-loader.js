async function loadTranslations() {
    const langs = ['en', 'zh', 'ja'];
    window.translations = {};

    const promises = langs.map(lang => 
        fetch(`i18n/${lang}.json`)
            .then(res => {
                if (!res.ok) throw new Error(`Failed to load ${lang}`);
                return res.json();
            })
            .then(data => {
                window.translations[lang] = data;
            })
            .catch(err => {
                console.warn(`Translation missing for ${lang}`, err);
                window.translations[lang] = {}; 
            })
    );

    await Promise.all(promises);
}

// Expose promise for main.js to wait on
window.translationLoader = loadTranslations();