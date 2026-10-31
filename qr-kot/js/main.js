(function () {
    'use strict';

    var translations = window.QRKOT_TRANSLATIONS || {};
    var supported = ['pl', 'en', 'pt-BR'];
    var defaultLang = 'en';
    var storageKey = 'qrkot-lang';
    var currentLang = defaultLang;

    var nav = document.getElementById('main-nav');
    var menuToggle = document.getElementById('menu-toggle');
    var menuToggleLabel = document.getElementById('menu-toggle-label');

    function isSupported(lang) {
        return supported.indexOf(lang) !== -1;
    }

    function readStoredLanguage() {
        try {
            return window.localStorage.getItem(storageKey);
        } catch (error) {
            return null;
        }
    }

    function saveLanguage(lang) {
        try {
            window.localStorage.setItem(storageKey, lang);
        } catch (error) {
            /* Storage can be unavailable in private modes; the page still works. */
        }
    }

    function readUrlLanguage() {
        try {
            return new URLSearchParams(window.location.search).get('lang');
        } catch (error) {
            return null;
        }
    }

    function updateUrl(lang) {
        try {
            var url = new URL(window.location.href);
            if (lang === defaultLang) {
                url.searchParams.delete('lang');
            } else {
                url.searchParams.set('lang', lang);
            }
            window.history.replaceState({}, '', url.toString());
        } catch (error) {
            /* Ignore environments where history updates are restricted. */
        }
    }

    function setMeta(selector, value) {
        var element = document.querySelector(selector);
        if (element) {
            element.setAttribute('content', value);
        }
    }

    function setMenuLabel() {
        if (!menuToggle || !menuToggleLabel) {
            return;
        }
        var dict = translations[currentLang] || translations[defaultLang];
        var isOpen = menuToggle.getAttribute('aria-expanded') === 'true';
        var label = dict[isOpen ? 'nav.close' : 'nav.menu'];
        menuToggleLabel.textContent = label;
        menuToggle.setAttribute('aria-label', label);
    }

    function applyLanguage(lang, options) {
        if (!isSupported(lang) || !translations[lang]) {
            lang = defaultLang;
        }

        var settings = options || {};
        var dict = translations[lang];
        currentLang = lang;

        document.documentElement.setAttribute('lang', lang);
        document.title = dict['meta.title'];

        setMeta('#meta-description', dict['meta.description']);
        setMeta('#og-title', dict['meta.ogTitle']);
        setMeta('#og-description', dict['meta.ogDescription']);
        setMeta('#og-locale', dict['meta.ogLocale']);
        setMeta('#twitter-title', dict['meta.ogTitle']);
        setMeta('#twitter-description', dict['meta.ogDescription']);
        setMeta('meta[property="og:image:alt"]', dict['hero.imageAlt']);

        document.querySelectorAll('[data-i18n]').forEach(function (element) {
            var key = element.getAttribute('data-i18n');
            if (Object.prototype.hasOwnProperty.call(dict, key)) {
                element.textContent = dict[key];
            }
        });

        document.querySelectorAll('[data-i18n-html]').forEach(function (element) {
            var key = element.getAttribute('data-i18n-html');
            if (Object.prototype.hasOwnProperty.call(dict, key)) {
                element.innerHTML = dict[key];
            }
        });

        document.querySelectorAll('[data-i18n-alt]').forEach(function (element) {
            var key = element.getAttribute('data-i18n-alt');
            if (Object.prototype.hasOwnProperty.call(dict, key)) {
                element.setAttribute('alt', dict[key]);
            }
        });

        document.querySelectorAll('[data-i18n-aria-label]').forEach(function (element) {
            var key = element.getAttribute('data-i18n-aria-label');
            if (Object.prototype.hasOwnProperty.call(dict, key)) {
                element.setAttribute('aria-label', dict[key]);
            }
        });

        document.querySelectorAll('[data-set-lang]').forEach(function (button) {
            var isActive = button.getAttribute('data-set-lang') === lang;
            button.classList.toggle('is-active', isActive);
            button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });

        setMenuLabel();

        if (settings.persist !== false) {
            saveLanguage(lang);
        }

        if (settings.updateUrl !== false) {
            updateUrl(lang);
        }
    }

    document.querySelectorAll('[data-set-lang]').forEach(function (button) {
        button.addEventListener('click', function () {
            applyLanguage(button.getAttribute('data-set-lang'));
        });
    });

    /* ---------- Mobile navigation ---------- */

    function setMenuState(isOpen) {
        if (!nav || !menuToggle) {
            return;
        }
        nav.classList.toggle('is-open', isOpen);
        menuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        setMenuLabel();
    }

    if (menuToggle && nav) {
        menuToggle.addEventListener('click', function () {
            setMenuState(menuToggle.getAttribute('aria-expanded') !== 'true');
        });

        nav.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () {
                setMenuState(false);
            });
        });

        document.addEventListener('click', function (event) {
            if (menuToggle.getAttribute('aria-expanded') !== 'true') {
                return;
            }
            if (event.target.closest('.header-actions')) {
                return;
            }
            if (!nav.contains(event.target)) {
                setMenuState(false);
            }
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && menuToggle.getAttribute('aria-expanded') === 'true') {
                setMenuState(false);
                menuToggle.focus();
            }
        });

        var desktopQuery = window.matchMedia('(min-width: 961px)');
        var handleDesktopChange = function (event) {
            if (event.matches) {
                setMenuState(false);
            }
        };
        if (typeof desktopQuery.addEventListener === 'function') {
            desktopQuery.addEventListener('change', handleDesktopChange);
        } else if (typeof desktopQuery.addListener === 'function') {
            desktopQuery.addListener(handleDesktopChange);
        }
    }

    /* ---------- Scroll reveal ---------- */

    var revealItems = document.querySelectorAll('.reveal');
    var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (revealItems.length && 'IntersectionObserver' in window && !prefersReducedMotion) {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

        revealItems.forEach(function (item) {
            observer.observe(item);
        });
    } else {
        revealItems.forEach(function (item) {
            item.classList.add('is-visible');
        });
    }

    /* ---------- Footer year ---------- */

    document.querySelectorAll('[data-year]').forEach(function (element) {
        element.textContent = String(new Date().getFullYear());
    });

    /* ---------- Initial language ---------- */

    var urlLang = readUrlLanguage();
    var storedLang = readStoredLanguage();
    var initialLang = isSupported(urlLang) ? urlLang : (isSupported(storedLang) ? storedLang : defaultLang);

    applyLanguage(initialLang, {
        persist: isSupported(storedLang),
        updateUrl: false
    });
})();
