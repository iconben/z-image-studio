        const form = document.getElementById('generateForm');
        const stepsInput = document.getElementById('steps');
        const stepsVal = document.getElementById('stepsVal');
        const generateBtn = document.getElementById('generateBtn');
        const previewContainer = document.getElementById('previewContainer');
        const resultInfo = document.getElementById('resultInfo');
        const downloadBtn = document.getElementById('downloadBtn');
        const timeTaken = document.getElementById('timeTaken');
        const metaDims = document.getElementById('metaDims');
        const metaSize = document.getElementById('metaSize');
        const metaSeed = document.getElementById('metaSeed');
        const languageDropdownBtn = document.getElementById('languageDropdown');
        let currentLanguage = 'en';
        const metaPrecision = document.getElementById('metaPrecision');
        const metaSteps = document.getElementById('metaSteps');
        const imageModal = new bootstrap.Modal(document.getElementById('imageModal'));
        const modalImage = document.getElementById('modalImage');
        const historyListOffcanvas = document.getElementById('historyList');
        const historyListSidebar = document.getElementById('historyListSidebar');
        const restoreDraftBtn = document.getElementById('restoreDraftBtn');
        const themeToggleButton = document.getElementById('themeToggleButton');
        if (window.themeSwitcher) {
            window.themeSwitcher.initTheme(themeToggleButton);
        }

        // Pinning UI Elements
        const pinHistoryBtn = document.getElementById('pinHistoryBtn');
        const unpinHistoryBtn = document.getElementById('unpinHistoryBtn');
        const historyDrawerEl = document.getElementById('historyDrawer');
        const historyDrawer = new bootstrap.Offcanvas(historyDrawerEl);

        let isDirty = false;
        let timerInterval;
        let isHistoryPinned = localStorage.getItem('zimage_history_pinned') === 'true';

        // Apply initial pin state
        if (isHistoryPinned) {
            document.body.classList.add('history-pinned');
        }

        function toggleHistoryPin(shouldPin) {
            isHistoryPinned = shouldPin;
            localStorage.setItem('zimage_history_pinned', shouldPin);
            
            if (shouldPin) {
                document.body.classList.add('history-pinned');
                historyDrawer.hide(); // Hide offcanvas if it's open
            } else {
                document.body.classList.remove('history-pinned');
            }
            // Reload history to ensure the correct container is populated/updated
            loadHistory();
        }

        pinHistoryBtn.addEventListener('click', () => toggleHistoryPin(true));
        unpinHistoryBtn.addEventListener('click', () => toggleHistoryPin(false));

        const { formatValueWithOneDecimal, formatFileSize, formatSmartDate } = window.zutils || {};

        
        let translations = window.translations || {}
        if (!translations.en) { console.error('Translations failed to load'); translations.en = {}; }
;


        function updateLanguage(lang) {
            currentLanguage = lang;
            languageDropdownBtn.textContent = lang.toUpperCase();
            const t = translations[lang];
            
            // Update Text Content
            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (t[key]) el.textContent = t[key];
            });

            // Update Placeholders
            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
                const key = el.getAttribute('data-i18n-placeholder');
                if (t[key]) el.placeholder = t[key];
            });

            // Update Tooltip Titles
            document.querySelectorAll('[data-i18n-title]').forEach(el => {
                const key = el.getAttribute('data-i18n-title');
                if (t[key]) el.setAttribute('title', t[key]);
            });
            
            // Re-render model options if needed to update descriptions
            if (window.availableModels) {
                renderModelOptions(window.availableModels, currentPrecisionValue); // Pass current value
            }

            // Save preference
            localStorage.setItem('zimage_lang', lang);
            
            // Update Input Values (like default prompt)
            document.querySelectorAll('[data-i18n-value]').forEach(el => {
                const key = el.getAttribute('data-i18n-value');
                if (t[key]) {
                    // Only set if prompt isn't already loaded from localStorage or user input
                    if (el.id === 'prompt' && localStorage.getItem('zimage_prompt')) {
                        // Do nothing, localStorage takes precedence
                    } else {
                        el.value = t[key];
                    }
                }
            });
            
            // Handle dynamic state text (like button loading state if active)
            if (generateBtn.disabled) {
                 generateBtn.textContent = t.generating_btn;
            }
        }

        // Init Language
        let initialLang = localStorage.getItem('zimage_lang');
        if (!initialLang) {
            const browserLang = navigator.language;
            if (browserLang.startsWith('zh')) {
                initialLang = 'zh';
            } else if (browserLang.startsWith('ja')) {
                initialLang = 'ja';
            } else {
                initialLang = 'en';
            }
        }
        updateLanguage(initialLang);

        document.querySelectorAll('.dropdown-item[data-lang]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const lang = e.target.getAttribute('data-lang');
                updateLanguage(lang);
                // Reinitialize tooltips after language change to update titles
                var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
                var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
                  return new bootstrap.Tooltip(tooltipTriggerEl);
                });
            });
        });

        // --- Persistence Logic (Restored) ---
        const promptInput = document.getElementById('prompt');
        const widthInput = document.getElementById('width');
        const heightInput = document.getElementById('height');
        const seedInput = document.getElementById('seedInput');
        const seedRandomRadio = document.getElementById('seedRandom');
        const seedFixedRadio = document.getElementById('seedFixed');
        let currentPrecisionValue = "q8"; // Default value, will be set by loadModels/localStorage
        const precisionDropdownButton = document.getElementById('precisionDropdownButton');
        const precisionDropdownMenu = document.getElementById('precisionDropdownMenu');


        // Load saved values (prompt, steps, width, height)
        if (localStorage.getItem('zimage_prompt')) promptInput.value = localStorage.getItem('zimage_prompt');
        
        if (localStorage.getItem('zimage_steps')) {
            const savedSteps = localStorage.getItem('zimage_steps');
            stepsInput.value = savedSteps;
            stepsVal.textContent = savedSteps;
        }

        if (localStorage.getItem('zimage_width')) widthInput.value = localStorage.getItem('zimage_width');
        if (localStorage.getItem('zimage_height')) heightInput.value = localStorage.getItem('zimage_height');
        
        // --- Models Loading Logic ---
        async function loadModels() {
            try {
                const res = await fetch('/models');
                const data = await res.json();
                
                // Capture device info
                if (data.device) {
                    window.currentDevice = data.device;
                } else if (data.device_info) { // Fallback if old structure exists
                    window.currentDevice = data.device_info.device;
                }
                // Capture default precision
                if (data.default_precision) {
                    window.defaultPrecision = data.default_precision;
                }

                const models = data.models || []; // Use 'models' list from the new response structure
                window.availableModels = models; // Cache for language switching
                
                // Determine initial precision value
                const savedPrecision = localStorage.getItem('zimage_precision');
                if (savedPrecision && models.some(m => m.precision === savedPrecision)) {
                    currentPrecisionValue = savedPrecision;
                } else if (window.defaultPrecision) {
                    currentPrecisionValue = window.defaultPrecision;
                } else {
                    currentPrecisionValue = 'q8'; // Fallback
                }

                renderModelOptions(models, currentPrecisionValue); // Pass current value to renderer
                
            } catch (e) {
                console.error("Failed to load models", e);
                // Fallback options for dropdown, if fetch fails
                const fallbackModels = [
                    { precision: "q8", recommended: true },
                    { precision: "full", recommended: false }
                ];
                window.availableModels = fallbackModels;
                currentPrecisionValue = "q8";
                renderModelOptions(fallbackModels, currentPrecisionValue);
            }
        }

        function renderModelOptions(models, selectedValue) {

            const t = translations[currentLanguage];
            
            precisionDropdownMenu.innerHTML = ''; // Clear existing options

            let displayLabelForButton = "Select Precision"; // Default for button text

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
                
                // Set active class and update button display if this is the selected value
                if (m.precision === selectedValue) {
                    button.classList.add('active');
                    displayLabelForButton = label;
                }

                // Event listener for each dropdown item
                button.addEventListener('click', (e) => {
                    // Check if event.target has data-value, if not, it's the <i> inside the button
                    const clickedElement = e.target.closest('[data-value]');
                    const newValue = clickedElement.getAttribute('data-value');
                    currentPrecisionValue = newValue; // Update our JS variable
                    localStorage.setItem('zimage_precision', newValue); // Persist
                    precisionDropdownButton.textContent = clickedElement.textContent; // Update button text
                    
                    // Remove active from all and add to clicked
                    precisionDropdownMenu.querySelectorAll('.dropdown-item').forEach(item => {
                        item.classList.remove('active');
                    });
                    clickedElement.classList.add('active');

                    isDirty = true; // Mark form as dirty
                });

                listItem.appendChild(button);
                precisionDropdownMenu.appendChild(listItem);

            });

            // Set the dropdown button's text to the selected precision's label
            precisionDropdownButton.textContent = displayLabelForButton;
        }

        loadModels(); // Trigger load of models immediately on page load


        // Load saved Seed State
        const savedSeedMode = localStorage.getItem('zimage_seed_mode');
        if (savedSeedMode === 'fixed') {
            seedFixedRadio.checked = true;
            const savedSeedValue = localStorage.getItem('zimage_seed_value');
            if (savedSeedValue) {
                seedInput.value = savedSeedValue;
            }
        } else {
            // Default to random if no explicit fixed mode or if saved mode is random
            seedRandomRadio.checked = true;
        }
        updateSeedState(); // Apply disabled state based on loaded mode

        // Seed State Logic
        function updateSeedState() {
            if (seedFixedRadio.checked) {
                seedInput.disabled = false;
                // If empty when switching to fixed, generate a random one as a starting point
                if (!seedInput.value) {
                     seedInput.value = Math.floor(Math.random() * 1000000000);
                }
                localStorage.setItem('zimage_seed_mode', 'fixed');
                localStorage.setItem('zimage_seed_value', seedInput.value);
            } else {
                seedInput.disabled = true;
                localStorage.setItem('zimage_seed_mode', 'random');
                localStorage.removeItem('zimage_seed_value'); // Clear value if random
            }
        }

        seedRandomRadio.addEventListener('change', updateSeedState);
        seedFixedRadio.addEventListener('change', updateSeedState);
        seedInput.addEventListener('input', () => { // Save seed value when input changes
            if (seedFixedRadio.checked) { // Only save if fixed mode is active
                localStorage.setItem('zimage_seed_value', seedInput.value);
            }
            isDirty = true;
        });
        
        // Save on change
        promptInput.addEventListener('input', (e) => {
            localStorage.setItem('zimage_prompt', e.target.value);
            isDirty = true;
        });
        
        stepsInput.addEventListener('input', (e) => {
            stepsVal.textContent = e.target.value;
            localStorage.setItem('zimage_steps', e.target.value);
            isDirty = true;
        });

        // Enforce multiples of 16 for dimensions + Save
        ['width', 'height'].forEach(id => {
            const el = document.getElementById(id);
            el.addEventListener('change', (e) => {
                let val = parseInt(e.target.value);
                if (isNaN(val)) val = 1280;
                // Snap to nearest multiple of 16
                val = Math.round(val / 16) * 16;
                if (val < 16) val = 16;
                e.target.value = val;
                
                // Save to storage
                localStorage.setItem(`zimage_${id}`, val);
                isDirty = true;
            });
        });

        // --- History Logic ---
        let historyOffset = 0;
        const historyLimit = 20;
        let historyTotal = 0;
        let isHistoryLoading = false;
        let historyObserver;

        async function loadHistory(append = false) {
            if (isHistoryLoading) return;
            
            if (!append) {
                historyOffset = 0;
                historyTotal = 0;
                // Clear lists immediately if reloading from scratch
                historyListOffcanvas.innerHTML = '';
                historyListSidebar.innerHTML = '';
            }

            isHistoryLoading = true;

            // Remove sentinel if it exists (so we don't trigger it while loading)
            removeSentinels();

            try {
                const res = await fetch(`/history?limit=${historyLimit}&offset=${historyOffset}`);
                
                // Read headers
                const totalStr = res.headers.get('X-Total-Count');
                if (totalStr) historyTotal = parseInt(totalStr);

                const items = await res.json();
                renderHistory(items, append);
                
                // Update offset for next batch
                historyOffset += items.length;

                // Re-attach sentinel if we have more data
                if (historyOffset < historyTotal) {
                    addSentinels();
                }

            } catch (e) {
                console.error("Failed to load history", e);
            } finally {
                isHistoryLoading = false;
            }
        }

        function removeSentinels() {
             document.querySelectorAll('.history-sentinel').forEach(el => el.remove());
        }

        function addSentinels() {
            // Add sentinel to BOTH lists
            [historyListOffcanvas, historyListSidebar].forEach(container => {
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
                containers.forEach(c => c.innerHTML = emptyMsg);
                return;
            }

            items.forEach(item => {
                const date = formatSmartDate(item.created_at);
                const shortPrompt = item.prompt.length > 60 ? item.prompt.substring(0, 60) + '...' : item.prompt;
                const imageUrl = `/outputs/${item.filename}`;
                
                // Using HTML string for easier dual-appending
                const itemHtml = `
                    <a href="#" class="list-group-item list-group-item-action d-flex gap-3 py-3 history-item-link">
                        <img src="${imageUrl}" alt="thumb" width="80" height="80" class="rounded object-fit-cover flex-shrink-0 bg-light" loading="lazy">
                        <div class="d-flex flex-column gap-1 w-100" style="min-width: 0;">
                            <h6 class="mb-0 small text-truncate">${shortPrompt}</h6>
                            <p class="mb-0 opacity-75 small">${item.width}x${item.height} · ${formatFileSize(item.file_size_kb, currentLanguage)}</p>
                            <small class="text-muted" style="line-height: 0.9rem">${date}</small>
                            <small class="text-muted" style="line-height: 0.9rem">${formatValueWithOneDecimal(item.generation_time)}s · ${item.precision} · ${item.steps} steps</small>
                        </div>
                        <button class="btn btn-sm btn-outline-secondary ms-auto delete-history-item" data-id="${item.id}" title="${translations[currentLanguage].delete_btn_tooltip}">
                            <i class="bi bi-trash"></i>
                        </button>
                    </a>
                `;

                containers.forEach(container => {
                    // Create a temp div to parse HTML
                    const temp = document.createElement('div');
                    temp.innerHTML = itemHtml;
                    const el = temp.firstElementChild;
                    
                    el.onclick = (e) => {
                        // Only trigger load if not clicking delete button
                        if (!e.target.closest('.delete-history-item')) {
                            e.preventDefault();
                            loadFromHistory(item);
                        }
                    };

                    // Add delete handler
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
                });
            });
        }

        async function deleteHistoryItem(itemId) {
            try {
                const res = await fetch(`/history/${itemId}`, {
                    method: 'DELETE'
                });
                if (!res.ok) throw new Error('Failed to delete history item');
                loadHistory(); // Reload history after deletion (resets to page 1)
            } catch (e) {
                console.error("Error deleting history item:", e);
                alert("Failed to delete item.");
            }
        }

        // Initialize Intersection Observer
        historyObserver = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !isHistoryLoading) {
                loadHistory(true); // Load next page
            }
        }, { rootMargin: '200px' });

        function loadFromHistory(item) {
            // Auto-stash if dirty
            if (isDirty) {
                localStorage.setItem('zimage_stash_prompt', promptInput.value);
                localStorage.setItem('zimage_stash_steps', stepsInput.value);
                localStorage.setItem('zimage_stash_width', widthInput.value);
                localStorage.setItem('zimage_stash_height', heightInput.value);
                localStorage.setItem('zimage_stash_seed_mode', seedRandomRadio.checked ? 'random' : 'fixed');
                localStorage.setItem('zimage_stash_seed_value', seedInput.value);
                localStorage.setItem('zimage_stash_precision', currentPrecisionValue); // Use currentPrecisionValue
                restoreDraftBtn.classList.remove('d-none');
            }
            isDirty = false; // Now we are in "clean" history state

            promptInput.value = item.prompt;
            stepsInput.value = item.steps;
            stepsVal.textContent = item.steps;
            widthInput.value = item.width;
            heightInput.value = item.height;
            
            // Restore Seed: Always display the seed value, but default to Random mode
            if (item.seed !== null && item.seed !== undefined) {
                seedInput.value = item.seed; // Populate the value
            } else {
                seedInput.value = ''; // Clear if no seed
            }
            seedRandomRadio.checked = true; // Force Random mode
            updateSeedState(); // Update disabled state and local storage consistently
            
            // Save to local storage as if user typed it (sync state)
            localStorage.setItem('zimage_prompt', item.prompt);
            localStorage.setItem('zimage_steps', item.steps);
            localStorage.setItem('zimage_width', item.width);
            localStorage.setItem('zimage_height', item.height);
            // Note: Precision is NOT restored from history to avoid overriding user preference

            // Show preview
            const imageUrl = `/outputs/${item.filename}`;
            
            previewContainer.innerHTML = '';
            const img = new Image();
            img.src = imageUrl;
            img.className = 'img-fluid';
            img.style.cursor = 'pointer';
            img.onclick = () => {
                modalImage.src = imageUrl;
                imageModal.show();
            };
            previewContainer.appendChild(img);
            
            downloadBtn.href = imageUrl;
            
            // Format meta info using current translations
            const t = translations[currentLanguage] || translations.en || {};
            const stepsLabel = t.steps_label || 'steps';
            timeTaken.textContent = t.time_taken.replace('{0}', formatValueWithOneDecimal(item.generation_time));
            metaDims.textContent = `${item.width}x${item.height}`;
            metaSize.textContent = formatFileSize(item.file_size_kb, currentLanguage, translations);
            metaSeed.textContent = `${t.seed_label || 'Seed'}: ${item.seed}`;
            metaPrecision.textContent = `${item.precision || 'full'}`; // Default to 'full' for old entries
            metaSteps.textContent = `${item.steps || ''} ${stepsLabel}`;
            
            resultInfo.classList.remove('d-none');
            
            // Close drawer if on mobile OR if not pinned
            if (!isHistoryPinned || window.innerWidth < 992) {
                const drawer = bootstrap.Offcanvas.getInstance(document.getElementById('historyDrawer'));
                if (drawer) drawer.hide();
            }
        }

        restoreDraftBtn.onclick = () => {
            if (localStorage.getItem('zimage_stash_prompt')) {
                promptInput.value = localStorage.getItem('zimage_stash_prompt');
                localStorage.setItem('zimage_prompt', promptInput.value);
            }
            if (localStorage.getItem('zimage_stash_steps')) {
                stepsInput.value = localStorage.getItem('zimage_stash_steps');
                stepsVal.textContent = stepsInput.value;
                localStorage.setItem('zimage_steps', stepsInput.value);
            }
            if (localStorage.getItem('zimage_stash_width')) {
                widthInput.value = localStorage.getItem('zimage_stash_width');
                localStorage.setItem('zimage_width', widthInput.value);
            }
            if (localStorage.getItem('zimage_stash_height')) {
                heightInput.value = localStorage.getItem('zimage_stash_height');
                localStorage.setItem('zimage_height', heightInput.value);
            }
            if (localStorage.getItem('zimage_stash_precision')) {
                currentPrecisionValue = localStorage.getItem('zimage_stash_precision'); // Use new variable
                localStorage.setItem('zimage_precision', currentPrecisionValue);
                // Re-render model options to update button text and active state
                renderModelOptions(window.availableModels, currentPrecisionValue);
            }
            if (localStorage.getItem('zimage_stash_seed_mode')) {
                const stashSeedMode = localStorage.getItem('zimage_stash_seed_mode');
                if (stashSeedMode === 'fixed') {
                    seedFixedRadio.checked = true;
                    seedInput.value = localStorage.getItem('zimage_stash_seed_value');
                } else {
                    seedRandomRadio.checked = true;
                }
                updateSeedState();
            }
            restoreDraftBtn.classList.add('d-none');
            isDirty = true; // Restored draft is dirty by definition
        };

        // Load history on startup
        loadHistory();

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const currentLang = currentLanguage;
            const t = translations[currentLang];
            
            isDirty = false; // Generation commits the state
            restoreDraftBtn.classList.add('d-none'); // Clear stash option on new generation
            
            // Determine Seed
            let seedVal = null;
            if (seedFixedRadio.checked) {
                seedVal = parseInt(seedInput.value);
                if (isNaN(seedVal)) seedVal = Math.floor(Math.random() * 2147483647);
            } else {
                // Random mode: Generate client-side to ensure history reproducibility
                seedVal = Math.floor(Math.random() * 2147483647);
            }
            
            // UI Loading State
            generateBtn.disabled = true;
            generateBtn.textContent = t.generating_btn;
            previewContainer.innerHTML = `
                <div class="d-flex flex-column align-items-center">
                    <div class="spinner-border text-primary loading-spinner" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="mt-2 text-muted small" id="runningTimer">0.0s</div>
                    <div class="mt-1 text-muted small">Seed: ${seedVal}</div>
                </div>
            `;
            resultInfo.classList.add('d-none');

            // Start Timer
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
                precision: currentPrecisionValue // Use new variable
            };

            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                clearInterval(timerInterval); // Stop timer

                if (!response.ok) throw new Error('Generation failed');

                const data = await response.json();
                
                // Update UI with result
                const img = new Image();
                img.onload = () => {
                    previewContainer.innerHTML = '';
                    img.style.cursor = 'pointer'; // Make the preview image clickable
                    img.onclick = () => {
                        modalImage.src = data.image_url;
                        imageModal.show();
                    };
                    previewContainer.appendChild(img);
                    
                    downloadBtn.href = data.image_url;
                    
                    // Format meta info
                    const tMeta = translations[currentLanguage] || translations.en || {};
                    const stepsLabelMeta = tMeta.steps_label || 'steps';
                    timeTaken.textContent = tMeta.time_taken.replace('{0}', formatValueWithOneDecimal(data.generation_time));
                    metaDims.textContent = `${data.width}x${data.height}`;
                    metaSize.textContent = formatFileSize(data.file_size_kb, currentLanguage, translations);
                    metaSeed.textContent = `${tMeta.seed_label || 'Seed'}: ${data.seed}`;
                    metaPrecision.textContent = `${data.precision}`;
                    metaSteps.textContent = `${(data.steps || payload.steps || '')} ${stepsLabelMeta}`;
                    
                    resultInfo.classList.remove('d-none');
                    
                    generateBtn.disabled = false;
                    generateBtn.textContent = t.generate_btn;
                    
                    // Refresh history
                    loadHistory();
                };
                img.onerror = () => {
                     throw new Error('Failed to load image');
                }
                img.src = data.image_url;

            } catch (err) {
                clearInterval(timerInterval); // Stop timer on error
                console.error(err);
                previewContainer.innerHTML = `<div class="text-danger">Error: ${err.message}</div>`;
                generateBtn.disabled = false;
                generateBtn.textContent = t.generate_btn;
            }
        });

        // Initialize tooltips on page load
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
        var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
          return new bootstrap.Tooltip(tooltipTriggerEl)
        })
    
