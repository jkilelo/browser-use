/**
 * Universal Event Handler for Framework-Aware Interactions
 * Can be injected into any webpage to handle React, Vue, Angular, etc.
 */

class UniversalEventHandler {
    constructor() {
        this.frameworkDetector = this.detectFramework();
    }

    detectFramework() {
        const frameworks = {
            react: !!(window.React || document.querySelector('[data-reactroot]') ||
                document.querySelector('*[data-react-*]') ||
                Object.keys(window).find(key => key.startsWith('__REACT'))),
            vue: !!(window.Vue || document.querySelector('[data-v-]') ||
                document.querySelector('*[data-server-rendered]')),
            angular: !!(window.ng || window.angular ||
                document.querySelector('[ng-app]') ||
                document.querySelector('*[ng-*]')),
            svelte: !!(document.querySelector('*[class*="svelte-"]'))
        };

        return Object.keys(frameworks).filter(key => frameworks[key]);
    }

    /**
     * Smart click that works across all frameworks
     */
    click(element, options = {}) {
        if (!element) throw new Error('Element not found');

        // Ensure element is in viewport
        element.scrollIntoView({ block: 'center', behavior: 'smooth' });

        // For React/controlled components
        if (this.frameworkDetector.includes('react')) {
            return this.reactClick(element);
        }

        // For Vue components
        if (this.frameworkDetector.includes('vue')) {
            return this.vueClick(element);
        }

        // Default enhanced click
        return this.enhancedClick(element);
    }

    reactClick(element) {
        // Handle React's synthetic event system
        const nativeEvent = new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
            view: window
        });

        // Trigger React's event system
        const reactEventKey = Object.keys(element).find(key =>
            key.startsWith('__reactInternalInstance') ||
            key.startsWith('_reactInternalFiber')
        );

        if (reactEventKey) {
            element.focus?.();
            element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
        }

        element.dispatchEvent(nativeEvent);
        return true;
    }

    vueClick(element) {
        // Vue event handling
        element.focus?.();
        element.dispatchEvent(new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
            view: window
        }));
        return true;
    }

    enhancedClick(element) {
        // Enhanced click for vanilla JS and other frameworks
        const events = ['mousedown', 'mouseup', 'click'];
        events.forEach(eventType => {
            element.dispatchEvent(new MouseEvent(eventType, {
                bubbles: true,
                cancelable: true,
                view: window
            }));
        });
        return true;
    }

    /**
     * Smart input that works across all frameworks
     */
    type(element, text, options = {}) {
        if (!element) throw new Error('Element not found');

        element.focus();

        // For React controlled components
        if (this.frameworkDetector.includes('react')) {
            return this.reactType(element, text);
        }

        // For Vue
        if (this.frameworkDetector.includes('vue')) {
            return this.vueType(element, text);
        }

        // Default typing
        return this.enhancedType(element, text);
    }

    reactType(element, text) {
        // Clear existing value
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;

        const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value'
        ).set;

        const setter = element.tagName === 'TEXTAREA' ?
            nativeTextAreaValueSetter : nativeInputValueSetter;

        // Set value via native setter (bypasses React's controlled component)
        setter.call(element, text);

        // Trigger React's synthetic events
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));

        // Additional events for complex components
        element.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true }));
        element.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));

        return true;
    }

    vueType(element, text) {
        // Set value
        element.value = text;

        // Vue event handling
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));

        return true;
    }

    enhancedType(element, text) {
        // Enhanced typing for vanilla JS
        element.value = text;

        const events = ['input', 'change', 'keyup'];
        events.forEach(eventType => {
            element.dispatchEvent(new Event(eventType, { bubbles: true }));
        });

        return true;
    }

    /**
     * Smart select handling for dropdowns
     */
    select(element, value) {
        if (!element) throw new Error('Element not found');

        if (element.tagName === 'SELECT') {
            return this.handleSelect(element, value);
        }

        // Handle custom select components (MUI, etc.)
        return this.handleCustomSelect(element, value);
    }

    handleSelect(element, value) {
        element.value = value;
        element.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
    }

    handleCustomSelect(element, value) {
        // Handle Material-UI, Ant Design, etc.
        this.click(element); // Open dropdown

        setTimeout(() => {
            // Find and click the option
            const option = document.querySelector(`[data-value="${value}"], [value="${value}"]`) ||
                Array.from(document.querySelectorAll('*')).find(el =>
                    el.textContent?.trim() === value
                );

            if (option) {
                this.click(option);
            }
        }, 100);

        return true;
    }

    /**
     * Smart checkbox/radio handling
     */
    check(element, checked = true) {
        if (!element) throw new Error('Element not found');

        if (element.type === 'checkbox' || element.type === 'radio') {
            element.checked = checked;
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.dispatchEvent(new Event('click', { bubbles: true }));
            return true;
        }

        // Handle custom checkbox components
        return this.click(element);
    }

    /**
     * Wait for element to be ready for interaction
     */
    waitForElement(selector, timeout = 5000) {
        return new Promise((resolve, reject) => {
            const element = document.querySelector(selector);
            if (element) {
                resolve(element);
                return;
            }

            const observer = new MutationObserver((mutations) => {
                const element = document.querySelector(selector);
                if (element) {
                    observer.disconnect();
                    resolve(element);
                }
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true
            });

            setTimeout(() => {
                observer.disconnect();
                reject(new Error(`Element ${selector} not found within ${timeout}ms`));
            }, timeout);
        });
    }
}

// Export for use in browser-use
window.UniversalEventHandler = UniversalEventHandler;

// Create global instance
window.universalEvents = new UniversalEventHandler();

// Convenience functions
window.smartClick = (element) => window.universalEvents.click(element);
window.smartType = (element, text) => window.universalEvents.type(element, text);
window.smartSelect = (element, value) => window.universalEvents.select(element, value);
window.smartCheck = (element, checked) => window.universalEvents.check(element, checked);
