(async function initApp() {
    console.log("Z-Image Studio: Starting initialization...");

    // Wait for translations
    if (window.translationLoader) {
        try {
            await window.translationLoader;
        } catch (e) {
            console.error("Error waiting for translations:", e);
        }
    }

    try {

        // --- Global DOM Elements ---
        const form = document.getElementById('generateForm');
        const stepsInput = document.getElementById('steps');
        const stepsVal = document.getElementById('stepsVal');
        const generateBtn = document.getElementById('generateBtn');
        const previewContainer = document.getElementById('previewContainer');
        const resultInfo = document.getElementById('resultInfo');
        const downloadBtn = document.getElementById('downloadBtn') || document.getElementById('downloadBtnMobile');
        const shareBtn = document.getElementById('shareBtn') || document.getElementById('shareBtnMobile');
        const copyBtn = document.getElementById('copyBtn') || document.getElementById('copyBtnMobile');
        const timeTaken = document.getElementById('timeTaken');
        const metaDims = document.getElementById('metaDims');
        const metaSize = document.getElementById('metaSize');
        const metaSeed = document.getElementById('metaSeed');
        const languageDropdownBtn = document.getElementById('languageDropdown');
        const metaPrecision = document.getElementById('metaPrecision');
        const metaSteps = document.getElementById('metaSteps');
        const metaLoras = document.getElementById('metaLoras');
        const shareToast = document.getElementById('shareToast');
        const toastMessage = document.getElementById('toastMessage');
        
        // Robust Bootstrap Check
        if (typeof bootstrap === 'undefined') {
            throw new Error("Bootstrap is not loaded. Check your internet connection or CDN.");
        }

        // Initialize tooltips for buttons
        function initTooltips() {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                // Destroy existing tooltip if it exists
                const existingTooltip = bootstrap.Tooltip.getInstance(tooltipTriggerEl);
                if (existingTooltip) {
                    existingTooltip.dispose();
                }
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }

        // Hide tooltip for a specific element
        function hideTooltip(element) {
            if (!element) return;

            const tooltip = bootstrap.Tooltip.getInstance(element);
            if (tooltip) {
                tooltip.hide();
            }
        }

        // Add tooltip auto-hide to button click events
        function addTooltipAutoHide(button) {
            if (!button) return;

            // Check if button has tooltip
            const hasTooltip = button.hasAttribute('data-bs-toggle') &&
                              button.getAttribute('data-bs-toggle') === 'tooltip' ||
                              button.hasAttribute('title');

            if (hasTooltip) {
                button.addEventListener('click', function() {
                    // Add a small delay to ensure the click event completes before hiding
                    setTimeout(() => {
                        hideTooltip(this);
                    }, 100);
                });
            }
        }

        // Initialize auto-hide tooltips for all buttons with tooltips
        function initTooltipAutoHide() {
            const buttons = document.querySelectorAll('button[title], button[data-bs-toggle="tooltip"]');
            buttons.forEach(button => {
                addTooltipAutoHide(button);
            });

            // Also handle anchor tags with tooltips (like download button)
            const anchors = document.querySelectorAll('a[title], a[data-bs-toggle="tooltip"]');
            anchors.forEach(anchor => {
                addTooltipAutoHide(anchor);
            });
        }

        const imageModalEl = document.getElementById('imageModal');
        const imageModal = imageModalEl ? new bootstrap.Modal(imageModalEl) : null;
        const modalImage = document.getElementById('modalImage');
        
        const historyListOffcanvas = document.getElementById('historyList');
        const historyListSidebar = document.getElementById('historyListSidebar');
        const restoreDraftBtn = document.getElementById('restoreDraftBtn');
        const themeToggleButton = document.getElementById('themeToggleButton');
        
        if (window.themeSwitcher && themeToggleButton) {
            window.themeSwitcher.initTheme(themeToggleButton);
        }

        // Pinning UI Elements
        const pinHistoryBtn = document.getElementById('pinHistoryBtn');
        const unpinHistoryBtn = document.getElementById('unpinHistoryBtn');
        const historyDrawerEl = document.getElementById('historyDrawer');
        const historyDrawer = historyDrawerEl ? new bootstrap.Offcanvas(historyDrawerEl) : null;

        // Refresh Buttons
        const refreshHistoryBtn = document.getElementById('refreshHistoryBtn');
        const refreshHistorySidebarBtn = document.getElementById('refreshHistorySidebarBtn');

        // Pull to Refresh Indicators
        const pullRefreshIndicator = document.getElementById('pullRefreshIndicator');
        const pullRefreshIndicatorSidebar = document.getElementById('pullRefreshIndicatorSidebar');

        // Precision Elements
        const precisionDropdownButton = document.getElementById('precisionDropdownButton');
        const precisionDropdownMenu = document.getElementById('precisionDropdownMenu');
        
        // Seed Elements
        const seedInput = document.getElementById('seedInput');
        const seedRandomRadio = document.getElementById('seedRandom');
        const seedFixedRadio = document.getElementById('seedFixed');

        // LoRA Elements
        const activeLoraList = document.getElementById('activeLoraList');
        const addLoraForm = document.getElementById('addLoraForm');
        const toggleAddLoraBtn = document.getElementById('toggleAddLoraBtn');
        const confirmAddLoraBtn = document.getElementById('confirmAddLoraBtn');
        const newLoraStrength = document.getElementById('newLoraStrength');
        const newLoraStrengthVal = document.getElementById('newLoraStrengthVal');
        const loraCountBadge = document.getElementById('loraCountBadge');
        
        const openLoraModalBtn = document.getElementById('openLoraModalBtn');
        const loraSelectionModalEl = document.getElementById('loraSelectionModal');
        const loraSelectionModal = loraSelectionModalEl ? new bootstrap.Modal(loraSelectionModalEl) : null;
        
        const loraListGroup = document.getElementById('loraListGroup');
        const loraSearchInput = document.getElementById('loraSearchInput');
        const loraLoading = document.getElementById('loraLoading');

        const pendingLoraDisplay = document.getElementById('pendingLoraDisplay');
        const pendingLoraName = document.getElementById('pendingLoraName');
        const clearPendingLoraBtn = document.getElementById('clearPendingLoraBtn');

        const uploadLoraBtn = document.getElementById('uploadLoraBtn');
        const loraFileInput = document.getElementById('loraFileInput');
        const uploadProgressContainer = document.getElementById('uploadProgressContainer');
        
        const loraDropZone = document.getElementById('loraDropZone'); 
        const loraDropOverlay = document.getElementById('loraDropOverlay');

        // Input Elements
        const promptInput = document.getElementById('prompt');
        const widthInput = document.getElementById('width');
        const heightInput = document.getElementById('height');

        // --- State Variables ---
        let isDirty = false;
        let timerInterval;
        let isHistoryPinned = localStorage.getItem('zimage_history_pinned') === 'true';
        let currentLanguage = 'en';
        let currentPrecisionValue = "q8";
        let activeLoras = []; 
        let cachedLoras = [];
        let pendingLora = null;
        let currentImageFilename = null;
        let currentImageUrl = null;
        let shareBtnMobile, copyBtnMobile; // Declare mobile buttons early to avoid hoisting issues

        // --- Search state management (matches API parameter names) ---
        const searchState = {
            q: '',
            start_date: '',
            end_date: '',
            debounceTimeout: null,
            currentRequest: null,  // AbortController for cancellation
            isLoading: false
        };

        // --- Logic ---

        // Apply initial pin state
        if (isHistoryPinned) {
            document.body.classList.add('history-pinned');
        }

        function toggleHistoryPin(shouldPin) {
            isHistoryPinned = shouldPin;
            localStorage.setItem('zimage_history_pinned', shouldPin);
            
            if (shouldPin) {
                document.body.classList.add('history-pinned');
                if (historyDrawer) historyDrawer.hide();
            } else {
                document.body.classList.remove('history-pinned');
            }
            // Reload history to ensure the correct container is populated/updated
            loadHistory();
        }

        if (pinHistoryBtn) pinHistoryBtn.addEventListener('click', () => toggleHistoryPin(true));
        if (unpinHistoryBtn) unpinHistoryBtn.addEventListener('click', () => toggleHistoryPin(false));

        // Refresh button event listeners
        if (refreshHistoryBtn) refreshHistoryBtn.addEventListener('click', refreshHistory);
        if (refreshHistorySidebarBtn) refreshHistorySidebarBtn.addEventListener('click', refreshHistory);

        // Search event listeners
        const toggleSearchBtn = document.getElementById('toggleSearchBtn');
        const toggleSearchSidebarBtn = document.getElementById('toggleSearchSidebarBtn');
        if (toggleSearchBtn) {
            toggleSearchBtn.addEventListener('click', () => toggleSearchContainer('drawer'));
        }
        if (toggleSearchSidebarBtn) {
            toggleSearchSidebarBtn.addEventListener('click', () => toggleSearchContainer('sidebar'));
        }

        const historySearchInput = document.getElementById('historySearchInput');
        const historySearchInputSidebar = document.getElementById('historySearchInputSidebar');
        const historyStartDateInput = document.getElementById('historyStartDate');
        const historyStartDateInputSidebar = document.getElementById('historyStartDateSidebar');
        const historyEndDateInput = document.getElementById('historyEndDate');
        const historyEndDateInputSidebar = document.getElementById('historyEndDateSidebar');

        if (historySearchInput) {
            historySearchInput.addEventListener('input', () => {
                searchState.q = historySearchInput.value.trim();
                if (historySearchInputSidebar) historySearchInputSidebar.value = searchState.q;
                updateClearButtonVisibility();
                scheduleSearch();
            });

            // Trigger search on Enter key
            historySearchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    searchState.q = historySearchInput.value.trim();
                    scheduleSearch();
                }
            });
        }

        if (historySearchInputSidebar) {
            historySearchInputSidebar.addEventListener('input', () => {
                searchState.q = historySearchInputSidebar.value.trim();
                if (historySearchInput) historySearchInput.value = searchState.q;
                updateClearButtonVisibility();
                scheduleSearch();
            });

            // Trigger search on Enter key
            historySearchInputSidebar.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    searchState.q = historySearchInputSidebar.value.trim();
                    scheduleSearch();
                }
            });
        }

        if (historyStartDateInput) {
            historyStartDateInput.addEventListener('change', () => {
                searchState.start_date = historyStartDateInput.value;
                if (historyStartDateInputSidebar) historyStartDateInputSidebar.value = searchState.start_date;
                updateClearButtonVisibility();
                scheduleSearch();
            });
        }

        if (historyStartDateInputSidebar) {
            historyStartDateInputSidebar.addEventListener('change', () => {
                searchState.start_date = historyStartDateInputSidebar.value;
                if (historyStartDateInput) historyStartDateInput.value = searchState.start_date;
                updateClearButtonVisibility();
                scheduleSearch();
            });
        }

        if (historyEndDateInput) {
            historyEndDateInput.addEventListener('change', () => {
                searchState.end_date = historyEndDateInput.value;
                if (historyEndDateInputSidebar) historyEndDateInputSidebar.value = searchState.end_date;
                updateClearButtonVisibility();
                scheduleSearch();
            });
        }

        if (historyEndDateInputSidebar) {
            historyEndDateInputSidebar.addEventListener('change', () => {
                searchState.end_date = historyEndDateInputSidebar.value;
                if (historyEndDateInput) historyEndDateInput.value = searchState.end_date;
                updateClearButtonVisibility();
                scheduleSearch();
            });
        }

        // Clear button handlers
        const clearSearchBtn = document.getElementById('clearSearchBtn');
        const clearSearchSidebarBtn = document.getElementById('clearSearchSidebarBtn');
        if (clearSearchBtn) {
            clearSearchBtn.addEventListener('click', () => {
                searchState.q = '';
                if (historySearchInput) historySearchInput.value = '';
                if (historySearchInputSidebar) historySearchInputSidebar.value = '';
                updateClearButtonVisibility();
                scheduleSearch();
            });
        }
        if (clearSearchSidebarBtn) {
            clearSearchSidebarBtn.addEventListener('click', () => {
                searchState.q = '';
                if (historySearchInput) historySearchInput.value = '';
                if (historySearchInputSidebar) historySearchInputSidebar.value = '';
                updateClearButtonVisibility();
                scheduleSearch();
            });
        }

        const clearStartDateBtn = document.getElementById('clearStartDateBtn');
        const clearStartDateSidebarBtn = document.getElementById('clearStartDateSidebarBtn');
        if (clearStartDateBtn) {
            clearStartDateBtn.addEventListener('click', () => {
                searchState.start_date = '';
                if (historyStartDateInput) historyStartDateInput.value = '';
                if (historyStartDateInputSidebar) historyStartDateInputSidebar.value = '';
                updateClearButtonVisibility();
                scheduleSearch();
            });
        }
        if (clearStartDateSidebarBtn) {
            clearStartDateSidebarBtn.addEventListener('click', () => {
                searchState.start_date = '';
                if (historyStartDateInput) historyStartDateInput.value = '';
                if (historyStartDateInputSidebar) historyStartDateInputSidebar.value = '';
                updateClearButtonVisibility();
                scheduleSearch();
            });
        }

        const clearEndDateBtn = document.getElementById('clearEndDateBtn');
        const clearEndDateSidebarBtn = document.getElementById('clearEndDateSidebarBtn');
        if (clearEndDateBtn) {
            clearEndDateBtn.addEventListener('click', () => {
                searchState.end_date = '';
                if (historyEndDateInput) historyEndDateInput.value = '';
                if (historyEndDateInputSidebar) historyEndDateInputSidebar.value = '';
                updateClearButtonVisibility();
                scheduleSearch();
            });
        }
        if (clearEndDateSidebarBtn) {
            clearEndDateSidebarBtn.addEventListener('click', () => {
                searchState.end_date = '';
                if (historyEndDateInput) historyEndDateInput.value = '';
                if (historyEndDateInputSidebar) historyEndDateInputSidebar.value = '';
                updateClearButtonVisibility();
                scheduleSearch();
            });
        }

        // Function to show/hide clear buttons based on input values
        function updateClearButtonVisibility() {
            const clearSearchBtn = document.getElementById('clearSearchBtn');
            const clearSearchSidebarBtn = document.getElementById('clearSearchSidebarBtn');
            const clearStartDateBtn = document.getElementById('clearStartDateBtn');
            const clearStartDateSidebarBtn = document.getElementById('clearStartDateSidebarBtn');
            const clearEndDateBtn = document.getElementById('clearEndDateBtn');
            const clearEndDateSidebarBtn = document.getElementById('clearEndDateSidebarBtn');
            const searchInput = document.getElementById('historySearchInput');
            const searchInputSidebar = document.getElementById('historySearchInputSidebar');
            const startDateInput = document.getElementById('historyStartDate');
            const startDateInputSidebar = document.getElementById('historyStartDateSidebar');
            const endDateInput = document.getElementById('historyEndDate');
            const endDateInputSidebar = document.getElementById('historyEndDateSidebar');

            // Determine if there's a search value (check both inputs)
            const hasSearchValue = (searchInput?.value.trim() || '') || (searchInputSidebar?.value.trim() || '');
            const hasStartDate = startDateInput?.value || startDateInputSidebar?.value;
            const hasEndDate = endDateInput?.value || endDateInputSidebar?.value;

            // Show/hide search clear button
            if (clearSearchBtn && searchInput) {
                if (searchInput.value.trim()) {
                    clearSearchBtn.classList.remove('d-none');
                } else {
                    clearSearchBtn.classList.add('d-none');
                }
            }
            if (clearSearchSidebarBtn && searchInputSidebar) {
                if (searchInputSidebar.value.trim()) {
                    clearSearchSidebarBtn.classList.remove('d-none');
                } else {
                    clearSearchSidebarBtn.classList.add('d-none');
                }
            }

            // Show/hide start date clear button
            if (clearStartDateBtn && startDateInput) {
                if (startDateInput.value) {
                    clearStartDateBtn.classList.remove('d-none');
                } else {
                    clearStartDateBtn.classList.add('d-none');
                }
            }
            if (clearStartDateSidebarBtn && startDateInputSidebar) {
                if (startDateInputSidebar.value) {
                    clearStartDateSidebarBtn.classList.remove('d-none');
                } else {
                    clearStartDateSidebarBtn.classList.add('d-none');
                }
            }

            // Show/hide end date clear button
            if (clearEndDateBtn && endDateInput) {
                if (endDateInput.value) {
                    clearEndDateBtn.classList.remove('d-none');
                } else {
                    clearEndDateBtn.classList.add('d-none');
                }
            }
            if (clearEndDateSidebarBtn && endDateInputSidebar) {
                if (endDateInputSidebar.value) {
                    clearEndDateSidebarBtn.classList.remove('d-none');
                } else {
                    clearEndDateSidebarBtn.classList.add('d-none');
                }
            }

            // Update search input tooltip with full text
            if (searchInput) {
                const tooltip = bootstrap.Tooltip.getInstance(searchInput);
                if (searchInput.value.trim()) {
                    searchInput.setAttribute('title', searchInput.value.trim());
                    if (tooltip) {
                        tooltip.dispose();
                        new bootstrap.Tooltip(searchInput);
                    }
                } else {
                    searchInput.setAttribute('title', translations[currentLanguage]?.history_search_aria || 'Search by keywords');
                    if (tooltip) {
                        tooltip.dispose();
                        new bootstrap.Tooltip(searchInput);
                    }
                }
            }
            if (searchInputSidebar) {
                const tooltip = bootstrap.Tooltip.getInstance(searchInputSidebar);
                if (searchInputSidebar.value.trim()) {
                    searchInputSidebar.setAttribute('title', searchInputSidebar.value.trim());
                    if (tooltip) {
                        tooltip.dispose();
                        new bootstrap.Tooltip(searchInputSidebar);
                    }
                } else {
                    searchInputSidebar.setAttribute('title', translations[currentLanguage]?.history_search_aria || 'Search by keywords');
                    if (tooltip) {
                        tooltip.dispose();
                        new bootstrap.Tooltip(searchInputSidebar);
                    }
                }
            }
        }

        // Initialize pull-to-refresh
        initPullToRefresh();

        const { formatValueWithOneDecimal, formatFileSize, formatSmartDate } = window.zutils || {};

        let translations = window.translations || { en: {} };

        // Initialize search from URL on startup (after translations are available)
        initSearchFromURL();

        function updateLanguage(lang) {
            currentLanguage = lang;
            if (languageDropdownBtn) languageDropdownBtn.textContent = lang.toUpperCase();

            // Highlight the selected language in the dropdown menu
            document.querySelectorAll('#languageDropdown + .dropdown-menu .dropdown-item').forEach((item) => {
                if (item.getAttribute('data-lang') === lang) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });

            // Enhanced fallback logic for missing translations
            let t = translations[lang];

            // If language not found, try fallbacks
            if (!t) {
                if (lang === 'zh') {
                    // Fallback for old zh key
                    t = translations['zh-CN'];
                }
                if (!t) {
                    // Final fallback to English
                    t = translations.en;
                    console.warn(`Language '${lang}' not found, falling back to English`);
                }
            }
            
            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (t[key]) el.textContent = t[key];
            });

            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
                const key = el.getAttribute('data-i18n-placeholder');
                if (t[key]) el.placeholder = t[key];
            });

            document.querySelectorAll('[data-i18n-title]').forEach(el => {
                const key = el.getAttribute('data-i18n-title');
                if (t[key]) el.setAttribute('title', t[key]);
            });
            
            // Update button text spans for icon buttons
            document.querySelectorAll('[data-i18n].button-text, [data-i18n].ms-1').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (t[key]) el.textContent = t[key];
            });
            
            if (window.availableModels) {
                renderModelOptions(window.availableModels, currentPrecisionValue);
            }

            localStorage.setItem('zimage_lang', lang);
            
            document.querySelectorAll('[data-i18n-value]').forEach(el => {
                const key = el.getAttribute('data-i18n-value');
                if (t[key]) {
                    if (el.id === 'prompt' && localStorage.getItem('zimage_prompt')) {
                        // Keep user value
                    } else {
                        el.value = t[key];
                    }
                }
            });
            
            renderActiveLoras();
            updateShareButtonState();
            
            if (generateBtn && generateBtn.disabled && t.generating_btn) {
                generateBtn.textContent = t.generating_btn;
            }
        }

        // Init Language
        let initialLang = localStorage.getItem('zimage_lang');

        // Migrate old language keys
        if (initialLang === 'zh') {
            initialLang = 'zh-CN'; // Migrate old Chinese to Simplified Chinese
            localStorage.setItem('zimage_lang', initialLang); // Update localStorage
        }

        if (!initialLang) {
            const browserLang = navigator.language;
            if (browserLang.startsWith('zh-CN')) initialLang = 'zh-CN';
            else if (browserLang.startsWith('zh-TW')) initialLang = 'zh-TW';
            else if (browserLang.startsWith('zh')) initialLang = 'zh-CN'; // Default to Simplified Chinese
            else if (browserLang.startsWith('ja')) initialLang = 'ja';
            else initialLang = 'en';
        }
        updateLanguage(initialLang);
        
        // Initialize tooltips after language is set
        initTooltips();
        // Initialize auto-hide tooltip functionality
        initTooltipAutoHide();

        document.querySelectorAll('.dropdown-item[data-lang]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const lang = e.target.getAttribute('data-lang');
                updateLanguage(lang);
                initTooltips();
                // Re-initialize auto-hide tooltip functionality after language change
                initTooltipAutoHide();
            });
        });

        // Load saved values
        if (localStorage.getItem('zimage_prompt') && promptInput) promptInput.value = localStorage.getItem('zimage_prompt');
        
        if (localStorage.getItem('zimage_steps') && stepsInput) {
            const savedSteps = localStorage.getItem('zimage_steps');
            stepsInput.value = savedSteps;
            if (stepsVal) stepsVal.textContent = savedSteps;
        }

        if (localStorage.getItem('zimage_width') && widthInput) widthInput.value = localStorage.getItem('zimage_width');
        if (localStorage.getItem('zimage_height') && heightInput) heightInput.value = localStorage.getItem('zimage_height');

        // Load saved LoRAs
        try {
            const savedLoras = localStorage.getItem('zimage_active_loras');
            if (savedLoras) {
                const parsed = JSON.parse(savedLoras);
                if (Array.isArray(parsed)) {
                    activeLoras = parsed;
                    console.log("Loaded active LoRAs:", activeLoras);
                }
            }
        } catch (e) {
            console.error("Failed to parse saved LoRAs", e);
            activeLoras = [];
        }

        function saveLorasState() {
            localStorage.setItem('zimage_active_loras', JSON.stringify(activeLoras));
            isDirty = true;
        }

        function renderActiveLoras() {
            if (!activeLoraList) return;
            activeLoraList.innerHTML = '';
            activeLoras.forEach((lora, index) => {
                const item = document.createElement('div');
                item.className = "card d-flex flex-row justify-content-between align-items-center p-2 shadow-sm";
                item.innerHTML = `
                    <div class="d-flex flex-column text-truncate me-2">
                        <span class="fw-medium text-truncate" title="${lora.display_name}">${lora.display_name}</span>
                        <small class="text-muted" style="font-size: 0.75rem;">Strength: ${lora.strength}</small>
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-danger border-0 remove-lora-btn" data-index="${index}" title="Remove">
                        <i class="bi bi-x-lg"></i>
                    </button>
                `;
                item.querySelector('.remove-lora-btn').addEventListener('click', () => {
                    activeLoras.splice(index, 1);
                    saveLorasState();
                    renderActiveLoras();
                    updateAddLoraState();
                });
                activeLoraList.appendChild(item);
            });

            if (loraCountBadge) loraCountBadge.textContent = `${activeLoras.length}/4`;
            updateAddLoraState();
        }

        function updateAddLoraState() {
            const isFull = activeLoras.length >= 4;

            if (toggleAddLoraBtn) {
                toggleAddLoraBtn.classList.toggle('opacity-50', isFull);
                toggleAddLoraBtn.classList.toggle('pe-none', isFull);
            }

            if (confirmAddLoraBtn) {
                if (isFull) {
                    confirmAddLoraBtn.disabled = true;
                } else {
                    confirmAddLoraBtn.disabled = !pendingLora;
                }
            }
        }

        function setPendingLora(filename, displayName) {
            pendingLora = { filename, display_name: displayName };
            if (pendingLoraName) pendingLoraName.textContent = displayName;
            if (pendingLoraDisplay) pendingLoraDisplay.classList.remove('d-none');
            if (confirmAddLoraBtn) confirmAddLoraBtn.disabled = false;
            if (loraDropZone) loraDropZone.classList.add('d-none'); // Hide the drop zone
        }

        function clearPendingLora() {
            pendingLora = null;
            if (pendingLoraDisplay) pendingLoraDisplay.classList.add('d-none');
            if (confirmAddLoraBtn) confirmAddLoraBtn.disabled = true;
            if (loraFileInput) loraFileInput.value = ''; 
            if (loraDropZone) loraDropZone.classList.remove('d-none'); // Show the drop zone
        }

        if (clearPendingLoraBtn) clearPendingLoraBtn.addEventListener('click', clearPendingLora);

        function addLora() {
            if (activeLoras.length >= 4 || !pendingLora) return;
            const strength = newLoraStrength ? parseFloat(newLoraStrength.value) : 1.0;
            activeLoras.push({ 
                filename: pendingLora.filename, 
                display_name: pendingLora.display_name, 
                strength 
            });
            saveLorasState();
            renderActiveLoras();
            
            // Reset form
            if (newLoraStrength) newLoraStrength.value = 1.0;
            if (newLoraStrengthVal) newLoraStrengthVal.textContent = "1.0";
            clearPendingLora();
        }

        if (confirmAddLoraBtn) confirmAddLoraBtn.addEventListener('click', addLora);
        
        if (newLoraStrength) {
            newLoraStrength.addEventListener('input', (e) => {
                if (newLoraStrengthVal) newLoraStrengthVal.textContent = e.target.value;
            });
        }

        // Modal & List Logic
        if (openLoraModalBtn) {
            openLoraModalBtn.addEventListener('click', () => {
                if (loraSelectionModal) loraSelectionModal.show();
                loadLoras(); // Fetch when opening
            });
        }

        async function loadLoras() {
            if (cachedLoras.length > 0) {
                renderLoraList(cachedLoras);
            }
            
            if (loraLoading) loraLoading.classList.remove('d-none');
            try {
                const res = await fetch('/loras');
                if (!res.ok) throw new Error('Failed to fetch LoRAs');
                cachedLoras = await res.json();
                renderLoraList(cachedLoras);
            } catch (e) {
                console.error("Error loading LoRAs:", e);
                const t = translations[currentLanguage] || translations.en || {};
                showToast(t.loras_load_error || "Failed to load LoRAs", true);

                if (loraListGroup) loraListGroup.innerHTML = `<div class="text-danger p-3">Failed to load LoRAs</div>`;
            } finally {
                if (loraLoading) loraLoading.classList.add('d-none');
            }
        }

        function renderLoraList(loras) {
            if (!loraListGroup) return;
            loraListGroup.innerHTML = '';
            
            const filter = loraSearchInput ? loraSearchInput.value.toLowerCase() : "";
            const filtered = loras.filter(l => l.display_name.toLowerCase().includes(filter));
            
            if (filtered.length === 0) {
                loraListGroup.innerHTML = `<div class="text-muted p-3 text-center">No LoRAs found</div>`;
                return;
            }

            filtered.forEach(l => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
                btn.innerHTML = `
                    <span>${l.display_name}</span>
                    <i class="bi bi-chevron-right text-muted small"></i>
                `;
                btn.onclick = () => {
                    setPendingLora(l.filename, l.display_name);
                    if (loraSelectionModal) loraSelectionModal.hide();
                };
                loraListGroup.appendChild(btn);
            });
        }

        if (loraSearchInput) loraSearchInput.addEventListener('input', () => renderLoraList(cachedLoras));

        // -- Drag and Drop Logic --
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            document.addEventListener(eventName, (e) => { e.preventDefault(); e.stopPropagation(); }, false);
        });

        if (loraDropZone) {
            ['dragenter', 'dragover'].forEach(eventName => {
                loraDropZone.addEventListener(eventName, highlight, false);
            });
            ['dragleave', 'drop'].forEach(eventName => {
                loraDropZone.addEventListener(eventName, unhighlight, false);
            });
            loraDropZone.addEventListener('drop', handleDrop, false);
        }

        function highlight() {
            if (loraDropOverlay) loraDropOverlay.classList.remove('d-none');
        }
        function unhighlight() {
            if (loraDropOverlay) loraDropOverlay.classList.add('d-none');
        }

        function handleDrop(e) {
            unhighlight();
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                if (files[0].name.endsWith('.safetensors')) {
                    uploadLoraFile(files[0]);
                } else {
                    alert("Only .safetensors files are supported for LoRA upload.");
                }
            }
        }

        if (uploadLoraBtn && loraFileInput) {
            uploadLoraBtn.addEventListener('click', () => loraFileInput.click());
            loraFileInput.addEventListener('change', (e) => {
                if (e.target.files.length) uploadLoraFile(e.target.files[0]);
            });
        }

        async function uploadLoraFile(file) {
            const formData = new FormData();
            formData.append('file', file);
            
            if (uploadProgressContainer) uploadProgressContainer.classList.remove('d-none');
            const progressBar = uploadProgressContainer ? uploadProgressContainer.querySelector('.progress-bar') : null;
            if (progressBar) progressBar.style.width = '0%';
            
            try {
                let progress = 0;
                const interval = setInterval(() => {
                    progress = Math.min(progress + 10, 90);
                    if (progressBar) progressBar.style.width = progress + '%';
                }, 100);

                const res = await fetch('/loras', {
                    method: 'POST',
                    body: formData
                });
                
                clearInterval(interval);
                if (progressBar) progressBar.style.width = '100%';
                
                if (!res.ok) throw new Error(await res.text());
                const data = await res.json();
                
                cachedLoras.push({ filename: data.filename, display_name: data.display_name });
                setPendingLora(data.filename, data.display_name);
                
                setTimeout(() => {
                    if (uploadProgressContainer) uploadProgressContainer.classList.add('d-none');
                    if (progressBar) progressBar.style.width = '0%';
                }, 1000);
                
            } catch (err) {
                alert("Upload failed: " + err.message);
                if (uploadProgressContainer) uploadProgressContainer.classList.add('d-none');
            } finally {
                if (loraFileInput) loraFileInput.value = '';
            }
        }

        // --- Models Loading Logic ---
        async function loadModels() {
            try {
                const res = await fetch('/models');
                const data = await res.json();
                
                if (data.device) window.currentDevice = data.device;
                if (data.default_precision) window.defaultPrecision = data.default_precision;

                const models = data.models || []; 
                window.availableModels = models; 
                
                const savedPrecision = localStorage.getItem('zimage_precision');
                if (savedPrecision && models.some(m => m.precision === savedPrecision)) {
                    currentPrecisionValue = savedPrecision;
                } else if (window.defaultPrecision) {
                    currentPrecisionValue = window.defaultPrecision;
                } else {
                    currentPrecisionValue = 'q8'; 
                }

                try {
                    renderModelOptions(models, currentPrecisionValue); 
                } catch (renderErr) {
                    console.error("Error rendering model options:", renderErr);
                }
                
            } catch (e) {
                console.error("Failed to load models", e);
                const t = translations[currentLanguage] || translations.en || {};
                showToast(t.models_load_error || "Failed to load models", true);

                const fallbackModels = [
                    { precision: "q8", recommended: true },
                    { precision: "full", recommended: false }
                ];
                window.availableModels = fallbackModels;
                currentPrecisionValue = "q8";
                try {
                    renderModelOptions(fallbackModels, currentPrecisionValue);
                } catch (renderErr) { console.error(renderErr); }
            }
        }

        function renderModelOptions(models, selectedValue) {
            const t = translations[currentLanguage];
            if (!precisionDropdownMenu) return;
            precisionDropdownMenu.innerHTML = ''; 

            let displayLabelForButton = "Select Precision"; 

            models.forEach(m => {
                let deviceKey = null;
                if (window.currentDevice) {
                    deviceKey = `model_desc_${m.precision}_${window.currentDevice}`;
                }
                const genericKey = `model_desc_${m.precision}`;
                let label = (deviceKey && t[deviceKey]) ? t[deviceKey] : (t[genericKey] || m.precision);

                if (m.recommended) {
                    label += t.model_recommended_suffix;
                }

                const listItem = document.createElement('li');
                const button = document.createElement('button');
                button.className = 'dropdown-item';
                button.type = 'button';
                button.setAttribute('data-value', m.precision);
                button.textContent = label;
                
                if (m.precision === selectedValue) {
                    button.classList.add('active');
                    displayLabelForButton = label;
                }

                button.addEventListener('click', (e) => {
                    const clickedElement = e.target.closest('[data-value]');
                    const newValue = clickedElement.getAttribute('data-value');
                    currentPrecisionValue = newValue; 
                    localStorage.setItem('zimage_precision', newValue); 
                    if (precisionDropdownButton) precisionDropdownButton.textContent = clickedElement.textContent; 
                    
                    precisionDropdownMenu.querySelectorAll('.dropdown-item').forEach(item => {
                        item.classList.remove('active');
                    });
                    clickedElement.classList.add('active');
                    isDirty = true; 
                });

                listItem.appendChild(button);
                precisionDropdownMenu.appendChild(listItem);
            });

            if (precisionDropdownButton) precisionDropdownButton.textContent = displayLabelForButton;
        }

        // Seed Logic
        const savedSeedMode = localStorage.getItem('zimage_seed_mode');
        if (savedSeedMode === 'fixed') {
            if (seedFixedRadio) seedFixedRadio.checked = true;
            const savedSeedValue = localStorage.getItem('zimage_seed_value');
            if (savedSeedValue && seedInput) seedInput.value = savedSeedValue;
        } else {
            if (seedRandomRadio) seedRandomRadio.checked = true;
        }
        updateSeedState();

        function updateSeedState() {
            if (seedFixedRadio && seedFixedRadio.checked) {
                if (seedInput) {
                    seedInput.disabled = false;
                    if (!seedInput.value) seedInput.value = Math.floor(Math.random() * 1000000000);
                    localStorage.setItem('zimage_seed_mode', 'fixed');
                    localStorage.setItem('zimage_seed_value', seedInput.value);
                }
            } else {
                if (seedInput) seedInput.disabled = true;
                localStorage.setItem('zimage_seed_mode', 'random');
                localStorage.removeItem('zimage_seed_value'); 
            }
        }

        if (seedRandomRadio) seedRandomRadio.addEventListener('change', updateSeedState);
        if (seedFixedRadio) seedFixedRadio.addEventListener('change', updateSeedState);
        if (seedInput) seedInput.addEventListener('input', () => {
            if (seedFixedRadio.checked) {
                localStorage.setItem('zimage_seed_value', seedInput.value);
            }
            isDirty = true;
        });
        
        if (promptInput) promptInput.addEventListener('input', (e) => {
            localStorage.setItem('zimage_prompt', e.target.value);
            isDirty = true;
        });
        
        if (stepsInput) stepsInput.addEventListener('input', (e) => {
            if (stepsVal) stepsVal.textContent = e.target.value;
            localStorage.setItem('zimage_steps', e.target.value);
            isDirty = true;
        });

        if (widthInput) widthInput.addEventListener('change', (e) => {
            let val = parseInt(e.target.value);
            if (isNaN(val)) val = 1280;
            val = Math.round(val / 16) * 16;
            if (val < 16) val = 16;
            e.target.value = val;
            localStorage.setItem(`zimage_width`, val);
            isDirty = true;
        });
        if (heightInput) heightInput.addEventListener('change', (e) => {
            let val = parseInt(e.target.value);
            if (isNaN(val)) val = 1280;
            val = Math.round(val / 16) * 16;
            if (val < 16) val = 16;
            e.target.value = val;
            localStorage.setItem(`zimage_height`, val);
            isDirty = true;
        });

        // --- Search Functions ---

        // Toggle search container visibility
        function toggleSearchContainer(location) {
            const containerId = location === 'sidebar'
                ? 'historySearchContainerSidebar'
                : 'historySearchContainer';
            const toggleBtnId = location === 'sidebar'
                ? 'toggleSearchSidebarBtn'
                : 'toggleSearchBtn';
            const container = document.getElementById(containerId);
            const toggleBtn = document.getElementById(toggleBtnId);
            const icon = toggleBtn?.querySelector('i');

            if (container?.classList.contains('d-none')) {
                // Open search container
                container.classList.remove('d-none');
                if (icon) {
                    icon.classList.remove('bi-search');
                    icon.classList.add('bi-chevron-up');
                }

                // Auto-expand date filter if there are date values
                if (searchState.start_date || searchState.end_date) {
                    const dateFilterCollapseId = location === 'sidebar'
                        ? 'historyDateRangeFilterSidebar'
                        : 'historyDateRangeFilter';
                    const dateFilterCollapse = document.getElementById(dateFilterCollapseId);
                    if (dateFilterCollapse) {
                        const collapse = bootstrap.Collapse.getOrCreateInstance(dateFilterCollapse);
                        collapse.show();
                    }
                }
            } else {
                // Close search container
                container?.classList.add('d-none');
                if (icon) {
                    icon.classList.remove('bi-chevron-up');
                    icon.classList.add('bi-search');
                }
            }
        }

        // Initialize from URL on page load
        function initSearchFromURL() {
            const params = new URLSearchParams(window.location.search);
            searchState.q = params.get('q') || '';
            searchState.start_date = params.get('start_date') || '';
            searchState.end_date = params.get('end_date') || '';

            // Update UI for both drawer and sidebar
            const searchInput = document.getElementById('historySearchInput');
            const searchInputSidebar = document.getElementById('historySearchInputSidebar');
            const startDateInput = document.getElementById('historyStartDate');
            const startDateInputSidebar = document.getElementById('historyStartDateSidebar');
            const endDateInput = document.getElementById('historyEndDate');
            const endDateInputSidebar = document.getElementById('historyEndDateSidebar');

            if (searchInput) searchInput.value = searchState.q;
            if (searchInputSidebar) searchInputSidebar.value = searchState.q;
            if (startDateInput) startDateInput.value = searchState.start_date;
            if (startDateInputSidebar) startDateInputSidebar.value = searchState.start_date;
            if (endDateInput) endDateInput.value = searchState.end_date;
            if (endDateInputSidebar) endDateInputSidebar.value = searchState.end_date;

            // Auto-expand search containers if URL has search params
            if (searchState.q || searchState.start_date || searchState.end_date) {
                const container = document.getElementById('historySearchContainer');
                const containerSidebar = document.getElementById('historySearchContainerSidebar');
                const toggleBtn = document.getElementById('toggleSearchBtn');
                const toggleBtnSidebar = document.getElementById('toggleSearchSidebarBtn');
                const icon = toggleBtn?.querySelector('i');
                const iconSidebar = toggleBtnSidebar?.querySelector('i');

                if (container) container.classList.remove('d-none');
                if (containerSidebar) containerSidebar.classList.remove('d-none');

                if (icon) {
                    icon.classList.remove('bi-search');
                    icon.classList.add('bi-chevron-up');
                }
                if (iconSidebar) {
                    iconSidebar.classList.remove('bi-search');
                    iconSidebar.classList.add('bi-chevron-up');
                }

                // Auto-expand date filter if there are date values
                if (searchState.start_date || searchState.end_date) {
                    const dateFilterCollapse = document.getElementById('historyDateRangeFilter');
                    const dateFilterCollapseSidebar = document.getElementById('historyDateRangeFilterSidebar');
                    if (dateFilterCollapse) {
                        const collapse = bootstrap.Collapse.getOrCreateInstance(dateFilterCollapse);
                        collapse.show();
                    }
                    if (dateFilterCollapseSidebar) {
                        const collapseSidebar = bootstrap.Collapse.getOrCreateInstance(dateFilterCollapseSidebar);
                        collapseSidebar.show();
                    }
                }
            }

            updateClearButtonVisibility();
        }

        // Update URL from current search state
        function updateURLFromSearchState() {
            const params = new URLSearchParams();
            if (searchState.q) params.set('q', searchState.q);
            if (searchState.start_date) params.set('start_date', searchState.start_date);
            if (searchState.end_date) params.set('end_date', searchState.end_date);

            const newUrl = `${window.location.pathname}?${params.toString()}`;
            window.history.pushState({}, '', newUrl);
        }

        // Check if any filters are active
        function hasActiveFilters() {
            return searchState.q || searchState.start_date || searchState.end_date;
        }

        // Debounced search with request cancellation
        function scheduleSearch() {
            // Cancel any in-flight request
            if (searchState.currentRequest) {
                searchState.currentRequest.abort();
                searchState.currentRequest = null;
            }

            // Clear previous debounce timeout
            if (searchState.debounceTimeout) {
                clearTimeout(searchState.debounceTimeout);
            }

            showLoadingState();

            // Debounce rapid changes (400ms)
            searchState.debounceTimeout = setTimeout(() => {
                executeSearch();
            }, 400);
        }

        // Execute search with current filters
        async function executeSearch() {
            // Reset infinite scroll state
            historyOffset = 0;
            historyTotal = 0;
            removeSentinels();

            // Clear existing results
            if (historyListOffcanvas) historyListOffcanvas.innerHTML = '';
            if (historyListSidebar) historyListSidebar.innerHTML = '';

            // Build query parameters
            const params = new URLSearchParams();
            params.set('limit', historyLimit);
            params.set('offset', historyOffset);

            if (searchState.q) params.set('q', searchState.q);
            if (searchState.start_date) params.set('start_date', searchState.start_date);
            if (searchState.end_date) params.set('end_date', searchState.end_date);

            try {
                // Create new AbortController for this request
                const controller = new AbortController();
                searchState.currentRequest = controller;
                searchState.isLoading = true;

                const response = await fetch(`/history?${params.toString()}`, {
                    signal: controller.signal
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                // Update total count from headers
                const totalStr = response.headers.get('X-Total-Count');
                if (totalStr) historyTotal = parseInt(totalStr);

                const items = await response.json();

                // Render results
                renderHistory(items, false);

                // Update offset for infinite scroll
                historyOffset += items.length;

                // Add sentinel for infinite scroll if there are more results
                if (historyOffset < historyTotal) {
                    addSentinels();
                }

                // Update URL to reflect current search state
                updateURLFromSearchState();

                // Show or hide result count based on filters
                if (hasActiveFilters()) {
                    showResultCount(historyOffset, historyTotal);
                } else {
                    hideResultCount();
                }

            } catch (error) {
                if (error.name !== 'AbortError') {
                    console.error('Search failed:', error);
                    showErrorState(error.message);
                }
            } finally {
                searchState.currentRequest = null;
                searchState.isLoading = false;
                hideLoadingState();
            }
        }

        // Show loading state
        function showLoadingState() {
            const searchButton = document.getElementById('historySearchButton');
            if (searchButton) {
                const icon = searchButton.querySelector('i');
                icon.classList.add('refresh-spin');
            }
        }

        // Hide loading state
        function hideLoadingState() {
            const searchButton = document.getElementById('historySearchButton');
            if (searchButton) {
                const icon = searchButton.querySelector('i');
                icon.classList.remove('refresh-spin');
            }
        }

        // Show result count
        function showResultCount(shown, total) {
            const infoElement = document.getElementById('searchResultsInfo');
            const infoElementSidebar = document.getElementById('searchResultsInfoSidebar');
            const t = translations[currentLanguage] || translations.en || {};
            const text = (t.history_results_count || '{total} results')
                .replace('{total}', total);
            if (infoElement) infoElement.textContent = text;
            if (infoElementSidebar) infoElementSidebar.textContent = text;
        }

        // Hide result count
        function hideResultCount() {
            const infoElement = document.getElementById('searchResultsInfo');
            const infoElementSidebar = document.getElementById('searchResultsInfoSidebar');
            if (infoElement) infoElement.textContent = '';
            if (infoElementSidebar) infoElementSidebar.textContent = '';
        }

        // Show error state
        function showErrorState(message) {
            const infoElement = document.getElementById('searchResultsInfo');
            const infoElementSidebar = document.getElementById('searchResultsInfoSidebar');
            const t = translations[currentLanguage] || translations.en || {};
            const errorMessage = `${t.history_error_generic || 'An error occurred'}: ${message}`;
            if (infoElement) {
                infoElement.textContent = errorMessage;
                infoElement.classList.add('text-danger');
            }
            if (infoElementSidebar) {
                infoElementSidebar.textContent = errorMessage;
                infoElementSidebar.classList.add('text-danger');
            }
        }

        // HTML escape helper
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // --- History Logic ---
        let historyOffset = 0;
        const historyLimit = 20;
        let historyTotal = 0;
        let isHistoryLoading = false;
        let historyObserver;

        async function deleteHistoryItem(itemId) {
            try {
                const res = await fetch(`/history/${itemId}`, { method: 'DELETE' });
                if (!res.ok) throw new Error('Failed to delete history item');
                loadHistory(); 
            } catch (e) {
                console.error("Error deleting history item:", e);
                alert("Failed to delete item.");
            }
        }

        function removeSentinels() {
            document.querySelectorAll('.history-sentinel').forEach(el => el.remove());
        }

        function addSentinels() {
            [historyListOffcanvas, historyListSidebar].forEach(container => {
                if (!container) return;
                const sentinel = document.createElement('div');
                sentinel.className = 'history-sentinel p-3 text-center text-muted small';
                sentinel.textContent = 'Loading more...';
                container.appendChild(sentinel);
                if (historyObserver) historyObserver.observe(sentinel);
            });
        }

        function renderHistory(items, append) {
            const containers = [historyListOffcanvas, historyListSidebar];

            if (items.length === 0 && !append) {
                const emptyMsg = `<div class="text-center text-muted p-3" data-i18n="history_empty">${translations[currentLanguage].history_empty}</div>`;
                containers.forEach(c => { if (c) c.innerHTML = emptyMsg; });
                return;
            }

            items.forEach(item => {
                const date = formatSmartDate(item.created_at, translations, currentLanguage);
                const shortPrompt = item.prompt.length > 60 ? item.prompt.substring(0, 60) + '...' : item.prompt;
                const imageUrl = `/outputs/${item.filename}`;
                
                const itemHtml = `
                    <a href="#" class="list-group-item list-group-item-action d-flex gap-3 py-3 history-item-link">
                        <img src="${imageUrl}" alt="thumb" width="80" height="80" class="rounded object-fit-cover flex-shrink-0 bg-light" loading="lazy">
                        <div class="d-flex flex-column gap-1 w-100" style="min-width: 0;">
                            <h6 class="mb-0 small text-truncate">${shortPrompt}</h6>
                            <p class="mb-0 opacity-75 small">${item.width}x${item.height} · ${formatFileSize(item.file_size_kb, currentLanguage, translations)}</p>
                            <small class="text-muted" style="line-height: 0.9rem">${date}</small>
                            <small class="text-muted" style="line-height: 0.9rem">${formatValueWithOneDecimal(item.generation_time)}s · ${item.precision} · ${item.steps} steps</small>
                        </div>
                        <button class="btn btn-sm btn-outline-secondary ms-auto delete-history-item" data-id="${item.id}" title="${translations[currentLanguage].delete_btn_tooltip}" data-bs-toggle="tooltip" data-bs-placement="top">
                            <i class="bi bi-trash"></i>
                        </button>
                    </a>
                `;

                containers.forEach(container => {
                    if (!container) return;
                    const temp = document.createElement('div');
                    temp.innerHTML = itemHtml;
                    const el = temp.firstElementChild;
                    
                    el.onclick = (e) => {
                        if (!e.target.closest('.delete-history-item')) {
                            e.preventDefault();
                            loadFromHistory(item);
                        }
                    };

                    const delBtn = el.querySelector('.delete-history-item');
                    delBtn.onclick = async (e) => {
                        e.stopPropagation(); 
                        e.preventDefault();
                        const btn = e.currentTarget;
                        if (btn.dataset.armed === "true") {
                            await deleteHistoryItem(item.id);
                        } else {
                            btn.dataset.armed = "true";
                            btn.classList.remove('btn-outline-secondary');
                            btn.classList.add('btn-danger');
                            btn.innerHTML = '<i class="bi bi-trash-fill"></i>';
                            setTimeout(() => {
                                if (document.body.contains(btn)) {
                                    btn.dataset.armed = "false";
                                    btn.classList.remove('btn-danger');
                                    btn.classList.add('btn-outline-secondary');
                                    btn.innerHTML = '<i class="bi bi-trash"></i>';
                                }
                            }, 3000);
                        }
                    };

                    container.appendChild(el);
                    
                    // Initialize tooltip for the delete button
                    const deleteBtnTooltip = el.querySelector('.delete-history-item');
                    if (deleteBtnTooltip) {
                        new bootstrap.Tooltip(deleteBtnTooltip);
                        // Add auto-hide tooltip functionality
                        addTooltipAutoHide(deleteBtnTooltip);
                    }
                });
            });
        }

        historyObserver = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !isHistoryLoading) {
                loadHistory(true);
            }
        }, { rootMargin: '200px' });

        async function loadHistory(append = false) {
            if (isHistoryLoading) return;

            // If we have active filters, use executeSearch instead
            if (searchState.q || searchState.start_date || searchState.end_date) {
                if (!append) {
                    executeSearch();
                } else {
                    await loadMoreFilteredResults();
                }
                return;
            }

            // Original infinite scroll logic for unfiltered case
            if (!append) {
                historyOffset = 0;
                historyTotal = 0;
                if (historyListOffcanvas) historyListOffcanvas.innerHTML = '';
                if (historyListSidebar) historyListSidebar.innerHTML = '';
            }

            isHistoryLoading = true;
            removeSentinels();

            try {
                const res = await fetch(`/history?limit=${historyLimit}&offset=${historyOffset}`);
                const totalStr = res.headers.get('X-Total-Count');
                if (totalStr) historyTotal = parseInt(totalStr);

                const items = await res.json();
                renderHistory(items, append);
                historyOffset += items.length;

                if (historyOffset < historyTotal) {
                    addSentinels();
                }
            } catch (e) {
                console.error("Failed to load history", e);
                const t = translations[currentLanguage] || translations.en || {};
                showToast(t.history_load_error || "Failed to load history", true);
            } finally {
                isHistoryLoading = false;
            }
        }

        async function loadMoreFilteredResults() {
            if (isHistoryLoading) return;
            isHistoryLoading = true;
            removeSentinels();

            const params = new URLSearchParams();
            params.set('limit', historyLimit);
            params.set('offset', historyOffset);

            if (searchState.q) params.set('q', searchState.q);
            if (searchState.start_date) params.set('start_date', searchState.start_date);
            if (searchState.end_date) params.set('end_date', searchState.end_date);

            try {
                const response = await fetch(`/history?${params.toString()}`);

                // Update total count from headers
                const totalStr = response.headers.get('X-Total-Count');
                if (totalStr) historyTotal = parseInt(totalStr);

                const items = await response.json();

                if (items.length > 0) {
                    renderHistory(items, true);
                    historyOffset += items.length;
                }

                // Add sentinel for infinite scroll if there are more results
                if (historyOffset < historyTotal) {
                    addSentinels();
                }

                // Update result count
                showResultCount(historyOffset, historyTotal);

            } catch (error) {
                console.error('Failed to load more results:', error);
            } finally {
                isHistoryLoading = false;
            }
        }

        // Refresh history function
        async function refreshHistory() {
            // Prevent multiple simultaneous refreshes
            if (isHistoryLoading) return;

            // Reset scroll position to top
            if (historyListOffcanvas) historyListOffcanvas.scrollTop = 0;
            if (historyListSidebar) historyListSidebar.scrollTop = 0;

            // Add loading state to refresh buttons
            setRefreshButtonLoading(true);

            // Clear search filters when refreshing
            searchState.q = '';
            searchState.start_date = '';
            searchState.end_date = '';

            const searchInput = document.getElementById('historySearchInput');
            const searchInputSidebar = document.getElementById('historySearchInputSidebar');
            const startDateInput = document.getElementById('historyStartDate');
            const startDateInputSidebar = document.getElementById('historyStartDateSidebar');
            const endDateInput = document.getElementById('historyEndDate');
            const endDateInputSidebar = document.getElementById('historyEndDateSidebar');

            if (searchInput) searchInput.value = '';
            if (searchInputSidebar) searchInputSidebar.value = '';
            if (startDateInput) startDateInput.value = '';
            if (startDateInputSidebar) startDateInputSidebar.value = '';
            if (endDateInput) endDateInput.value = '';
            if (endDateInputSidebar) endDateInputSidebar.value = '';

            updateClearButtonVisibility();
            const searchResultsInfo = document.getElementById('searchResultsInfo');
            const searchResultsInfoSidebar = document.getElementById('searchResultsInfoSidebar');
            if (searchResultsInfo) {
                searchResultsInfo.textContent = '';
                searchResultsInfo.classList.remove('text-danger');
            }
            if (searchResultsInfoSidebar) {
                searchResultsInfoSidebar.textContent = '';
                searchResultsInfoSidebar.classList.remove('text-danger');
            }

            // Close search containers for both drawer and sidebar
            const container = document.getElementById('historySearchContainer');
            const containerSidebar = document.getElementById('historySearchContainerSidebar');
            const toggleBtn = document.getElementById('toggleSearchBtn');
            const toggleBtnSidebar = document.getElementById('toggleSearchSidebarBtn');
            const icon = toggleBtn?.querySelector('i');
            const iconSidebar = toggleBtnSidebar?.querySelector('i');

            if (container) container.classList.add('d-none');
            if (containerSidebar) containerSidebar.classList.add('d-none');
            if (icon) {
                icon.classList.remove('bi-chevron-up');
                icon.classList.add('bi-search');
            }
            if (iconSidebar) {
                iconSidebar.classList.remove('bi-chevron-up');
                iconSidebar.classList.add('bi-search');
            }

            // Clear URL
            window.history.pushState({}, '', window.location.pathname);

            try {
                // Load fresh first page (same as initial page load)
                await loadHistory(false);
            } catch (e) {
                console.error("Failed to refresh history", e);
                const t = translations[currentLanguage] || translations.en || {};
                showToast(t.history_load_error || "Failed to load history", true);
            } finally {
                // Remove loading state from refresh buttons
                setRefreshButtonLoading(false);
            }
        }

        // Set refresh button loading state
        function setRefreshButtonLoading(isLoading) {
            const buttons = [refreshHistoryBtn, refreshHistorySidebarBtn];
            buttons.forEach(btn => {
                if (!btn) return;

                const icon = btn.querySelector('i');
                if (!icon) return;

                if (isLoading) {
                    icon.classList.add('refresh-spin');
                    btn.disabled = true;
                } else {
                    icon.classList.remove('refresh-spin');
                    btn.disabled = false;
                }
            });

            // Add/remove visual spacing during refresh
            const historyContainers = [historyListOffcanvas, historyListSidebar];
            const indicators = [pullRefreshIndicator, pullRefreshIndicatorSidebar];

            historyContainers.forEach((container, index) => {
                if (!container) return;

                if (isLoading) {
                    // Add spacing during any refresh (button or pull-to-refresh)
                    container.classList.add('with-refresh-indicator');

                    // For pull-to-refresh, also make indicator visible
                    if (indicators[index] && !indicators[index].classList.contains('active')) {
                        indicators[index].classList.add('active', 'loading');
                        const t = translations[currentLanguage] || translations.en || {};
                        indicators[index].querySelector('span').textContent = t.refreshing_history || 'Refreshing...';
                    }
                } else {
                    // Remove spacing after refresh
                    container.classList.remove('with-refresh-indicator');
                    if (indicators[index]) {
                        // Hide indicator after a delay
                        setTimeout(() => {
                            if (indicators[index]) {
                                indicators[index].classList.remove('active', 'loading');
                            }
                        }, 300);
                    }
                }
            });
        }

        // Initialize pull-to-refresh functionality
        function initPullToRefresh() {
            // Pull-to-refresh state
            let isPulling = false;
            let startY = 0;
            let currentY = 0;
            let pullDistance = 0;
            const pullThreshold = 80; // Distance needed to trigger refresh

            // Function to setup pull-to-refresh for a container
            function setupPullToRefresh(container, indicator) {
                if (!container || !indicator) return;

                let isPulling = false;
                let startY = 0;

                container.addEventListener('touchstart', (e) => {
                    // Only start pull if at top of scroll
                    if (container.scrollTop <= 0) {
                        isPulling = true;
                        startY = e.touches[0].clientY;
                        indicator.classList.remove('active', 'loading');
                    }
                }, { passive: true });

                container.addEventListener('touchmove', (e) => {
                    if (!isPulling || isHistoryLoading) return;

                    currentY = e.touches[0].clientY;
                    pullDistance = currentY - startY;

                    if (pullDistance > 0) {
                        e.preventDefault(); // Prevent normal scroll behavior

                        const t = translations[currentLanguage] || translations.en || {};
                        const progress = Math.min(pullDistance / pullThreshold, 1);

                        if (progress < 0.6) {
                            indicator.classList.add('active');
                            indicator.classList.remove('loading');
                            container.classList.add('with-refresh-indicator');
                            indicator.querySelector('span').textContent = t.pull_to_refresh || 'Pull to refresh';
                        } else {
                            indicator.classList.add('active', 'ready');
                            container.classList.add('with-refresh-indicator');
                            indicator.querySelector('span').textContent = t.release_to_refresh || 'Release to refresh';
                        }
                    }
                });

                container.addEventListener('touchend', () => {
                    if (!isPulling) return;
                    isPulling = false;

                    if (pullDistance >= pullThreshold) {
                        // Trigger refresh
                        indicator.classList.add('loading');
                        indicator.classList.remove('ready');
                        const t = translations[currentLanguage] || translations.en || {};
                        indicator.querySelector('span').textContent = t.refreshing_history || 'Refreshing...';

                        // Refresh function already handles spacing through setRefreshButtonLoading
                        refreshHistory().finally(() => {
                            // Spacing cleanup handled by setRefreshButtonLoading
                        });
                    } else {
                        // Hide indicator and remove spacing
                        indicator.classList.remove('active', 'ready');
                        container.classList.remove('with-refresh-indicator');
                    }

                    pullDistance = 0;
                }, { passive: true });
            }

            // Setup pull-to-refresh for both containers
            setupPullToRefresh(historyListOffcanvas, pullRefreshIndicator);
            setupPullToRefresh(historyListSidebar, pullRefreshIndicatorSidebar);
        }

        function loadFromHistory(item) {
            
            // Stash current state
            if (isDirty) {
                if (promptInput) localStorage.setItem('zimage_stash_prompt', promptInput.value);
                if (stepsInput) localStorage.setItem('zimage_stash_steps', stepsInput.value);
                if (widthInput) localStorage.setItem('zimage_stash_width', widthInput.value);
                if (heightInput) localStorage.setItem('zimage_stash_height', heightInput.value);
                localStorage.setItem('zimage_stash_seed_mode', seedRandomRadio.checked ? 'random' : 'fixed');
                if (seedInput) localStorage.setItem('zimage_stash_seed_value', seedInput.value);
                localStorage.setItem('zimage_stash_precision', currentPrecisionValue);
                localStorage.setItem('zimage_stash_active_loras', JSON.stringify(activeLoras));
                if (restoreDraftBtn) restoreDraftBtn.classList.remove('d-none');
            }
            isDirty = false;

            if (promptInput) promptInput.value = item.prompt;
            if (stepsInput) {
                stepsInput.value = item.steps;
                if (stepsVal) stepsVal.textContent = item.steps;
            }
            if (widthInput) widthInput.value = item.width;
            if (heightInput) heightInput.value = item.height;
            
            // Restore LoRAs
            activeLoras = []; 
            if (item.loras && Array.isArray(item.loras)) {
                item.loras.forEach(l => {
                    activeLoras.push({
                        filename: l.filename,
                        display_name: l.display_name || l.filename,
                        strength: l.strength
                    });
                });
            } else if (item.lora_filename) {
                activeLoras.push({
                    filename: item.lora_filename,
                    display_name: item.lora_name || item.lora_filename,
                    strength: item.lora_strength
                });
            }
            saveLorasState();
            renderActiveLoras();

            // Seed
            if (item.seed !== null && item.seed !== undefined) {
                if (seedInput) seedInput.value = item.seed;
            } else {
                if (seedInput) seedInput.value = '';
            }
            if (seedRandomRadio) seedRandomRadio.checked = true; 
            updateSeedState();
            
            // Sync LocalStorage
            localStorage.setItem('zimage_prompt', item.prompt);
            localStorage.setItem('zimage_steps', item.steps);
            localStorage.setItem('zimage_width', item.width);
            localStorage.setItem('zimage_height', item.height);

            // Preview
            const imageUrl = `/outputs/${item.filename}`;
            if (previewContainer) {
                previewContainer.innerHTML = '';
                const img = new Image();
                img.src = imageUrl;
                img.className = 'img-fluid';
                img.style.cursor = 'pointer';
                img.onclick = () => {
                    if (modalImage) modalImage.src = imageUrl;
                    if (imageModal) imageModal.show();
                };
                previewContainer.appendChild(img);
            }
            if (downloadBtn) downloadBtn.href = `/download/${encodeURIComponent(item.filename)}`;
            // Update current image info for sharing
            currentImageFilename = item.filename;
            currentImageUrl = imageUrl;
            

            
            // Enable share/copy buttons now that we have an image
            updateShareButtonState();
            
            // Check button state after update
            setTimeout(() => {
                console.log('Button state after loadFromHistory:', {
                    shareBtnDisabled: shareBtn ? shareBtn.disabled : 'N/A',
                    copyBtnDisabled: copyBtn ? copyBtn.disabled : 'N/A',
                    shareBtnTitle: shareBtn ? shareBtn.title : 'N/A',
                    copyBtnTitle: copyBtn ? copyBtn.title : 'N/A'
                });
            }, 100);
            
            // Meta
            const t = translations[currentLanguage] || translations.en || {};
            const stepsLabel = t.steps_label || 'steps';
            if (timeTaken) timeTaken.textContent = t.time_taken.replace('{0}', formatValueWithOneDecimal(item.generation_time));
            if (metaDims) metaDims.textContent = `${item.width}x${item.height}`;
            if (metaSize) metaSize.textContent = formatFileSize(item.file_size_kb, currentLanguage, translations);
            if (metaSeed) metaSeed.textContent = `${t.seed_label || 'Seed'}: ${item.seed}`;
            if (metaPrecision) metaPrecision.textContent = `${item.precision || 'full'}`;
            if (metaSteps) metaSteps.textContent = `${item.steps || ''} ${stepsLabel}`;
            
            if (metaLoras) {
                if (activeLoras.length > 0) {
                    const loraLabel = t.lora_label || "LoRA";
                    const loraMeta = activeLoras.map(l => `${l.display_name} (${l.strength})`).join(', ');
                    metaLoras.textContent = `${loraLabel}: ${loraMeta}`;
                } else {
                    metaLoras.textContent = '';
                }
            }
            
            if (resultInfo) resultInfo.classList.remove('d-none');
            
            // Close drawer if mobile or unpinned
            if (!isHistoryPinned || window.innerWidth < 992) {
                if (historyDrawer) historyDrawer.hide();
            }
            
            // Update share button state after loading history image
            updateShareButtonState();
        }

        if (restoreDraftBtn) {
            restoreDraftBtn.onclick = () => {
                if (localStorage.getItem('zimage_stash_prompt') && promptInput) {
                    promptInput.value = localStorage.getItem('zimage_stash_prompt');
                    localStorage.setItem('zimage_prompt', promptInput.value);
                }
                // ... (Assuming simplified restore logic for brevity in this fix block)
                // Ideally restore all fields similar to loadFromHistory
                if (restoreDraftBtn) restoreDraftBtn.classList.add('d-none');
                isDirty = true;
            };
        }

        console.log("Z-Image Studio: Running startup load...");
        await Promise.all([
            loadModels(), 
            loadHistory()
        ]);
        renderActiveLoras(); 

        // --- Share and Copy Functionality ---
        
        // Toast notification helper
        function showToast(message, isError = false) {
            if (!shareToast || !toastMessage) return;
            
            toastMessage.textContent = message;
            if (isError) {
                shareToast.classList.add('text-bg-danger');
                shareToast.classList.remove('text-bg-success');
            } else {
                shareToast.classList.add('text-bg-success');
                shareToast.classList.remove('text-bg-danger');
            }
            
            const toast = new bootstrap.Toast(shareToast, {
                autohide: true,
                delay: 3000
            });
            toast.show();
        }
        
        // Feature detection for sharing capabilities
        function canShareUrl() {
            return navigator.share;
        }
        
        function canCopyToClipboard() {
            return navigator.clipboard && navigator.clipboard.write;
        }
        
        // Update button state based on feature support and image availability
        function updateShareButtonState() {
            const t = translations[currentLanguage] || translations.en || {};
            const hasImage = !!currentImageUrl;
            
            // Update all button instances (desktop and mobile)
            const allShareButtons = [shareBtn, shareBtnMobile].filter(btn => btn !== null && btn !== undefined);
            const allCopyButtons = [copyBtn, copyBtnMobile].filter(btn => btn !== null && btn !== undefined);
            const allDownloadButtons = [downloadBtn].filter(btn => btn !== null && btn !== undefined);
            
            // Enable/disable buttons based on image availability
            allShareButtons.forEach(btn => btn.disabled = !hasImage);
            allCopyButtons.forEach(btn => btn.disabled = !hasImage);
            allDownloadButtons.forEach(btn => btn.disabled = !hasImage);
            
            // Update tooltips based on context
            if (!hasImage) {
                allShareButtons.forEach(btn => {
                    refreshTooltip(btn, t.no_image_to_share || "No image available to share");
                });
                allCopyButtons.forEach(btn => {
                    refreshTooltip(btn, t.no_image_to_copy || "No image available to copy");
                });
                allDownloadButtons.forEach(btn => {
                    refreshTooltip(btn, t.no_image_to_download || "No image available to download");
                });
                return;
            }
            
            // Add tooltips to explain requirements
            if (window.isSecureContext) {
                // We can't know file sharing capability until we try with actual file,
                // so just indicate sharing is available
                const shareTitle = canShareUrl() ? (t.share_tooltip || "Share using your device options") : 
                                  (t.share_not_supported || "Sharing not supported");
                const copyTitle = canCopyToClipboard() ? (t.copy_tooltip || "Copy the image to your clipboard") : 
                                  (t.copy_not_supported || "Clipboard not supported");
                const downloadTitle = t.download_tooltip || "Download using your browser";
                
                allShareButtons.forEach(btn => {
                    refreshTooltip(btn, shareTitle);
                });
                allCopyButtons.forEach(btn => {
                    refreshTooltip(btn, copyTitle);
                });
                allDownloadButtons.forEach(btn => {
                    refreshTooltip(btn, downloadTitle);
                });
            } else {
                const secureTitle = t.share_requires_https || "Requires HTTPS or localhost";
                allShareButtons.forEach(btn => {
                    refreshTooltip(btn, secureTitle);
                });
                allCopyButtons.forEach(btn => {
                    refreshTooltip(btn, secureTitle);
                });
                // Download buttons don't require HTTPS, so keep the normal tooltip
                allDownloadButtons.forEach(btn => {
                    refreshTooltip(btn, downloadTitle);
                });
            }
        }
        
        // Helper: rebuild tooltip with an explicit title so stale instances don't linger
        function refreshTooltip(btn, title) {
            if (!btn) return;
            
            btn.setAttribute('title', title);
            // Bootstrap caches the original title in data attributes; clear them
            btn.removeAttribute('data-bs-original-title');
            btn.removeAttribute('data-bs-title');

            // Always dispose existing tooltip if it exists
            const existingTooltip = bootstrap.Tooltip.getInstance(btn);
            if (existingTooltip) {
                existingTooltip.dispose();
            }
            
            // Create new tooltip with the explicit title option to avoid stale cached values
            const tooltip = new bootstrap.Tooltip(btn, { title });

            // Add auto-hide tooltip functionality
            addTooltipAutoHide(btn);
        }
        
        async function shareImage() {
            if (!currentImageFilename || !currentImageUrl) {
                const t = translations[currentLanguage] || translations.en || {};
                showToast(t.no_image_to_share || "No image available to share", true);
                return;
            }
            
            const t = translations[currentLanguage] || translations.en || {};
            
            // Check if we're in a secure context (required for Web Share API)
            if (!window.isSecureContext) {
                showToast(t.share_requires_https || "Sharing requires a secure connection (HTTPS or localhost)", true);
                return;
            }
            
            // Check if Web Share API is available at all
            if (!navigator.share) {
                showToast(t.share_not_supported || "Sharing not supported in this browser", true);
                return;
            }
            
            try {
                // Fetch the image as a blob first
                const response = await fetch(currentImageUrl);
                if (!response.ok) throw new Error("Failed to fetch image");
                
                const blob = await response.blob();
                const file = new File([blob], currentImageFilename, { type: blob.type });
                
                // Now check if file sharing is supported with the actual file
                let canShareFiles = false;
                try {
                    canShareFiles = navigator.canShare && navigator.canShare({ files: [file] });
                } catch (e) {
                    console.warn("File sharing not supported:", e);
                    canShareFiles = false;
                }
                
                if (canShareFiles) {
                    // Share the file directly
                    await navigator.share({
                        files: [file],
                        title: currentImageFilename,
                        text: t.share_btn || "Check out this image I generated!"
                    });
                    console.log("Image shared successfully");
                } else {
                    // Fallback to sharing just the URL
                    await navigator.share({
                        title: currentImageFilename,
                        text: t.share_btn || "Check out this image I generated!",
                        url: currentImageUrl
                    });
                    console.log("Image URL shared successfully");
                }
                
            } catch (error) {
                console.error("Share failed:", error);
                if (error.name !== 'AbortError') { // Don't show error if user cancelled
                    showToast(t.share_error || "Failed to share image: " + error.message, true);
                }
            }
        }
        
        async function copyImageToClipboard() {
            if (!currentImageFilename || !currentImageUrl) {
                const t = translations[currentLanguage] || translations.en || {};
                showToast(t.no_image_to_copy || "No image available to copy", true);
                return;
            }
            
            const t = translations[currentLanguage] || translations.en || {};
            
            // Check if we're in a secure context (required for Clipboard API)
            if (!window.isSecureContext) {
                showToast(t.copy_requires_https || "Clipboard access requires a secure connection (HTTPS or localhost)", true);
                return;
            }
            
            // Check if Clipboard API is supported
            if (!navigator.clipboard || !navigator.clipboard.write) {
                showToast(t.copy_not_supported || "Clipboard access not supported", true);
                return;
            }
            
            // Check if ClipboardItem is supported
            if (typeof ClipboardItem === 'undefined') {
                showToast(t.copy_not_supported || "Clipboard access not supported", true);
                return;
            }
            
            try {
                // Fetch the image as a blob
                const response = await fetch(currentImageUrl);
                if (!response.ok) throw new Error("Failed to fetch image");
                
                const blob = await response.blob();
                
                // Create clipboard item
                let clipboardItem;
                try {
                    clipboardItem = new ClipboardItem({
                        [blob.type]: blob
                    });
                } catch (e) {
                    console.warn("ClipboardItem constructor failed, trying alternative approach:", e);
                    // Fallback for browsers that don't support ClipboardItem constructor
                    const item = {};
                    item[blob.type] = blob;
                    clipboardItem = new ClipboardItem(item);
                }
                
                // Write to clipboard
                await navigator.clipboard.write([clipboardItem]);
                
                showToast(t.copy_success || "Image copied to clipboard!");
                console.log("Image copied to clipboard successfully");
                
            } catch (error) {
                console.error("Copy to clipboard failed:", error);
                showToast(t.copy_error || "Failed to copy image to clipboard: " + error.message, true);
            }
        }
        
        // Set up event listeners for share and copy buttons
        if (shareBtn) {
            shareBtn.addEventListener('click', shareImage);
        }
        
        if (copyBtn) {
            copyBtn.addEventListener('click', copyImageToClipboard);
        }
        
        // Initialize mobile buttons if they exist and aren't already assigned to desktop vars
        shareBtnMobile = document.getElementById('shareBtnMobile');
        copyBtnMobile = document.getElementById('copyBtnMobile');
        
        if (shareBtnMobile && shareBtn !== shareBtnMobile) {
            shareBtnMobile.addEventListener('click', shareImage);
        }
        
        if (copyBtnMobile && copyBtn !== copyBtnMobile) {
            copyBtnMobile.addEventListener('click', copyImageToClipboard);
        }
        
        // Initialize share button state
        updateShareButtonState();
        
        if (form) {
                form.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    
                    // Auto-add pending LoRA if user forgot to click Add
                    if (pendingLora && activeLoras.length < 4) {
                        addLora();
                    }
            
                    const t = translations[currentLanguage] || translations.en || {};
                    
                    isDirty = false;                if (restoreDraftBtn) restoreDraftBtn.classList.add('d-none'); 
                
                let seedVal = null;
                if (seedFixedRadio && seedFixedRadio.checked) {
                    seedVal = parseInt(seedInput.value);
                    if (isNaN(seedVal)) seedVal = crypto.getRandomValues(new Uint32Array(1))[0];
                } else {
                    seedVal = crypto.getRandomValues(new Uint32Array(1))[0];
                }
                
                if (generateBtn) {
                    generateBtn.disabled = true;
                    generateBtn.textContent = t.generating_btn;
                }
                if (previewContainer) {
                    previewContainer.innerHTML = `
                        <div class="d-flex flex-column align-items-center">
                            <div class="spinner-border text-primary loading-spinner" role="status"></div>
                            <div class="mt-2 text-muted small" id="runningTimer">0.0s</div>
                            <div class="mt-1 text-muted small">Seed: ${seedVal}</div>
                        </div>
                    `;
                }
                if (resultInfo) resultInfo.classList.add('d-none');

                const startTime = Date.now();
                const timerEl = document.getElementById('runningTimer');
                if (timerInterval) clearInterval(timerInterval);
                timerInterval = setInterval(() => {
                    const elapsed = (Date.now() - startTime) / 1000;
                    if (timerEl) timerEl.textContent = formatValueWithOneDecimal(elapsed) + 's';
                }, 100);

                const payload = {
                    prompt: document.getElementById('prompt').value,
                    steps: parseInt(document.getElementById('steps').value),
                    width: parseInt(document.getElementById('width').value),
                    height: parseInt(document.getElementById('height').value),
                    seed: seedVal,
                    precision: currentPrecisionValue,
                    loras: activeLoras.map(l => ({ filename: l.filename, strength: parseFloat(l.strength) }))
                };

                try {
                    const response = await fetch('/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });

                    clearInterval(timerInterval);

                    if (!response.ok) throw new Error('Generation failed');

                    const data = await response.json();
                    
                    const img = new Image();
                    img.onload = () => {
                        if (previewContainer) {
                            previewContainer.innerHTML = '';
                            img.style.cursor = 'pointer';
                            img.onclick = () => {
                                if (modalImage) modalImage.src = data.image_url;
                                if (imageModal) imageModal.show();
                            };
                            previewContainer.appendChild(img);
                        }
                        if (downloadBtn) {
                            const filename = data.image_url.split('/').pop();
                            downloadBtn.href = `/download/${encodeURIComponent(filename)}`;
                            // Update current image info for sharing
                            currentImageFilename = filename;
                            currentImageUrl = data.image_url;
                            
                            // Enable share/copy buttons now that we have an image
                            updateShareButtonState();
                        }
                        
                        const tMeta = translations[currentLanguage] || translations.en || {};
                        const stepsLabelMeta = tMeta.steps_label || 'steps';
                        
                        if (timeTaken) timeTaken.textContent = tMeta.time_taken.replace('{0}', formatValueWithOneDecimal(data.generation_time));
                        if (metaDims) metaDims.textContent = `${data.width}x${data.height}`;
                        if (metaSize) metaSize.textContent = formatFileSize(data.file_size_kb, currentLanguage, translations);
                        if (metaSeed) metaSeed.textContent = `${tMeta.seed_label || 'Seed'}: ${data.seed}`;
                        if (metaPrecision) metaPrecision.textContent = `${data.precision}`;
                        if (metaSteps) metaSteps.textContent = `${(data.steps || payload.steps || '')} ${stepsLabelMeta}`;
                        
                        if (metaLoras) {
                            if (data.loras && data.loras.length > 0) {
                                const loraLabel = t.lora_label || "LoRA";
                                const loraMeta = data.loras.map(l => {
                                    const exists = cachedLoras.find(cl => cl.filename === l.filename);
                                    const name = exists ? exists.display_name : l.filename;
                                    return `${name} (${l.strength})`;
                                }).join(', ');
                                metaLoras.textContent = `${loraLabel}: ${loraMeta}`;
                            } else {
                                metaLoras.textContent = '';
                            }
                        }
                        
                        if (resultInfo) resultInfo.classList.remove('d-none');
                        if (generateBtn) {
                            generateBtn.disabled = false;
                            generateBtn.textContent = t.generate_btn;
                        }
                        
                        loadHistory();
                    };
                    img.onerror = () => { throw new Error('Failed to load image'); }
                    img.src = data.image_url;

                } catch (err) {
                    clearInterval(timerInterval);
                    console.error(err);
                    if (previewContainer) previewContainer.innerHTML = `<div class="text-danger">Error: ${err.message}</div>`;
                    if (generateBtn) {
                        generateBtn.disabled = false;
                        generateBtn.textContent = t.generate_btn;
                    }
                }
            });
        }

    } catch (err) {
        console.error("Initialization error:", err);
        alert("Application initialization failed. Please check the console.");
    }

})();
