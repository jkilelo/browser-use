"""
Robust JavaScript utility functions for browser interactions.
These are injected into pages to provide reliable interaction methods.
"""

JS_UTILS = """
// Browser-Use Utility Library - Robust interaction methods
window.BrowserUseUtils = {
    
    // ROBUST INPUT - Works with React/Vue/Formik controlled components
    input: function(selector, text) {
        const el = typeof selector === 'string' ? document.querySelector(selector) : selector;
        if (!el) return false;
        
        // Focus first
        el.focus();
        
        // Clear existing if needed
        if (el.value) {
            el.select();
            document.execCommand('delete');
        }
        
        // Use native setter for React compatibility
        const descriptor = Object.getOwnPropertyDescriptor(el.constructor.prototype, 'value') ||
                          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
        if (descriptor && descriptor.set) {
            descriptor.set.call(el, '');
        }
        
        // Type character by character with proper events
        for (let char of text) {
            // Keyboard events
            el.dispatchEvent(new KeyboardEvent('keydown', {key: char, bubbles: true}));
            el.dispatchEvent(new KeyboardEvent('keypress', {key: char, bubbles: true}));
            
            // Update value
            if (descriptor && descriptor.set) {
                descriptor.set.call(el, el.value + char);
            } else {
                el.value += char;
            }
            
            // Input event with proper data
            el.dispatchEvent(new InputEvent('input', {data: char, bubbles: true}));
            el.dispatchEvent(new KeyboardEvent('keyup', {key: char, bubbles: true}));
        }
        
        // Final events for React/Vue
        el.dispatchEvent(new Event('change', {bubbles: true}));
        el.dispatchEvent(new Event('blur', {bubbles: true}));
        
        return true;
    },
    
    // ROBUST CLICK - Simple reliable clicking
    click: function(selector) {
        const el = typeof selector === 'string' ? document.querySelector(selector) : selector;
        if (!el) return false;
        
        el.scrollIntoView({behavior: 'instant', block: 'center'});
        el.click();
        return true;
    },
    
    // ROBUST DOUBLE-CLICK - Works with Shadow DOM and timing requirements
    doubleClick: function(selector) {
        const el = typeof selector === 'string' ? document.querySelector(selector) : selector;
        if (!el) return false;
        
        el.scrollIntoView({behavior: 'instant', block: 'center'});
        const rect = el.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        
        // First click sequence
        ['mousemove', 'mouseover', 'mouseenter', 'mousedown', 'mouseup', 'click'].forEach(type => {
            el.dispatchEvent(new MouseEvent(type, {
                bubbles: true, cancelable: true, clientX: x, clientY: y,
                view: window, detail: type === 'click' ? 1 : 0
            }));
        });
        
        // Second click sequence with delay
        setTimeout(() => {
            ['mousedown', 'mouseup', 'click'].forEach(type => {
                el.dispatchEvent(new MouseEvent(type, {
                    bubbles: true, cancelable: true, clientX: x, clientY: y,
                    view: window, detail: type === 'click' ? 1 : 0
                }));
            });
            
            // Final double-click event
            el.dispatchEvent(new MouseEvent('dblclick', {
                bubbles: true, cancelable: true, clientX: x, clientY: y,
                view: window, detail: 2
            }));
        }, 50);
        
        return true;
    },
    
    // ROBUST SELECT - Works with custom dropdowns and React selects
    select: function(selector, optionValue) {
        const el = typeof selector === 'string' ? document.querySelector(selector) : selector;
        if (!el) return false;
        
        // Handle standard select
        if (el.tagName === 'SELECT') {
            el.focus();
            
            // Find option by value or text
            for (let i = 0; i < el.options.length; i++) {
                if (el.options[i].value === optionValue || 
                    el.options[i].textContent.trim() === optionValue) {
                    el.selectedIndex = i;
                    break;
                }
            }
            
            // Dispatch events for React/Vue
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new Event('input', {bubbles: true}));
            return true;
        }
        
        // Handle custom dropdowns (Material-UI, etc.)
        this.click(el); // Open dropdown
        
        // Wait for options to appear, then click the matching one
        setTimeout(() => {
            const option = Array.from(document.querySelectorAll('[role="option"]')).find(opt => 
                opt.textContent.trim() === optionValue
            );
            if (option) this.click(option);
        }, 100);
        
        return true;
    },
    
    // ROBUST CHECKBOX/RADIO - Works with custom components
    check: function(selector, checked = true) {
        const el = typeof selector === 'string' ? document.querySelector(selector) : selector;
        if (!el) return false;
        
        if (el.checked !== checked) {
            el.click(); // Use click for custom components
            
            // Also set property for React/Vue
            el.checked = checked;
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new Event('input', {bubbles: true}));
        }
        
        return true;
    },
    
    // COORDINATE-BASED HELPERS
    clickAt: function(x, y) {
        const el = document.elementFromPoint(x, y);
        if (!el) return false;
        
        el.click();
        return true;
    },
    
    inputAt: function(x, y, text) {
        const el = document.elementFromPoint(x, y);
        if (!el) return false;
        
        return this.input(el, text);
    },
    
    doubleClickAt: function(x, y) {
        const el = document.elementFromPoint(x, y);
        if (!el) return false;
        
        return this.doubleClick(el);
    },
    
    // FORM SUBMISSION - Handles validation and success detection
    submitForm: function(formSelector) {
        const form = typeof formSelector === 'string' ? document.querySelector(formSelector) : formSelector;
        if (!form) return {success: false, error: 'Form not found'};
        
        // Try submit button first
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]') ||
                         Array.from(form.querySelectorAll('button')).find(btn => 
                             btn.textContent.toLowerCase().includes('submit') || 
                             btn.textContent.toLowerCase().includes('send'));
        
        if (submitBtn) {
            this.click(submitBtn);
        } else {
            form.submit();
        }
        
        // Check for success indicators
        setTimeout(() => {
            const bodyText = document.body.innerText.toLowerCase();
            const hasSuccess = bodyText.includes('success') || 
                             bodyText.includes('thank') || 
                             bodyText.includes('submitted') ||
                             bodyText.includes('complete');
            
            window._lastSubmitResult = {
                success: hasSuccess,
                url: window.location.href,
                bodySnippet: document.body.innerText.substring(0, 500)
            };
        }, 500);
        
        return {success: true, message: 'Submitted, check _lastSubmitResult after 500ms'};
    },
    
    // VALIDATION HELPER - Check form validation state
    checkValidation: function(formSelector) {
        const form = typeof formSelector === 'string' ? document.querySelector(formSelector) : formSelector;
        if (!form) return {valid: false, errors: ['Form not found']};
        
        const invalidElements = Array.from(form.querySelectorAll(':invalid, .is-invalid, .error'));
        const errors = invalidElements.map(el => ({
            id: el.id || el.name,
            message: el.validationMessage || el.textContent || 'Invalid'
        }));
        
        return {
            valid: errors.length === 0,
            errors: errors
        };
    }
};

// Shorthand aliases for common use
window.input = window.BrowserUseUtils.input;
window.click = window.BrowserUseUtils.click;
window.doubleClick = window.BrowserUseUtils.doubleClick;
window.select = window.BrowserUseUtils.select;
window.check = window.BrowserUseUtils.check;
window.clickAt = window.BrowserUseUtils.clickAt;
window.inputAt = window.BrowserUseUtils.inputAt;
window.doubleClickAt = window.BrowserUseUtils.doubleClickAt;
""".strip()
