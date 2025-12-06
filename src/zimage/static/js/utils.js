(function () {
    function formatValueWithOneDecimal(value) {
        if (value === null || typeof value === 'undefined') return '';
        const fixed = Number(value).toFixed(1);
        return parseFloat(fixed);
    }

    function formatFileSize(fileSizeKb, lang, translations) {
        const allTranslations = translations || window.translations || {};
        const t = lang ? allTranslations[lang] : null;
        if (!t) return '';
        if (fileSizeKb >= 1024) {
            return t.meta_size_mb.replace('{0}', formatValueWithOneDecimal(fileSizeKb / 1024));
        }
        return t.meta_size.replace('{0}', formatValueWithOneDecimal(fileSizeKb));
    }

    function formatSmartDate(dateString, translations, currentLanguage) {
        const date = new Date(dateString);
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        const itemDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());

        if (itemDate.getTime() === today.getTime()) {
            return date.toLocaleTimeString();
        }
        if (itemDate.getTime() === yesterday.getTime()) {
            const t = translations && translations[currentLanguage];
            const yesterdayText = t && t.yesterday ? t.yesterday : 'Yesterday';
            return `${yesterdayText}, ${date.toLocaleTimeString()}`;
        }
        return date.toLocaleString();
    }

    window.zutils = {
        formatValueWithOneDecimal,
        formatFileSize,
        formatSmartDate
    };
})();
