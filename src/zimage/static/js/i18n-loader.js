(function loadTranslationsSync() {
    const langs = ['en', 'zh', 'ja'];
    const translations = {};
    langs.forEach((lang) => {
        try {
            const xhr = new XMLHttpRequest();
            xhr.open('GET', `i18n/${lang}.json`, false);
            xhr.send(null);
            if (xhr.status >= 200 && xhr.status < 300) {
                translations[lang] = JSON.parse(xhr.responseText);
            } else {
                console.error('Failed to load translations', lang, xhr.status);
            }
        } catch (err) {
            console.error('Error loading translations', lang, err);
        }
    });
    window.translations = translations;
})();
