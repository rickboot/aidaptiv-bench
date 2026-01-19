# Development Pitfalls: Python-to-JS Embedding

This project serves its UI directly from `dashboard.py` using multi-line Python strings. This architecture creates several critical "footguns" regarding string escaping and syntax collisions.

## 1. The "Literal Newline" Error
**Situation:** You write `csv.split('\n')` inside a Python template string.
**The Bug:** Python processes the `\n` into a physical "Enter" key press before sending it to the browser.
**Resulting UI Crash:** The browser receives malformed JavaScript that breaks the entire script engine:
```javascript
const lines = csv.split('
'); // ❌ Uncaught SyntaxError: Invalid or unexpected token
```
**The Fix:** 
- Use `String.fromCharCode(10)` instead of `\n` for JS string splitting.
- Use Python Raw Strings (`r"""..."""`) for templates to preserve backslashes.

## 2. Braces Collision (`{}`)
**Situation:** Using an f-string (`f"""..."""`) for the HTML template.
**The Bug:** Python tries to interpret every CSS rule and JS object (which use `{}`) as a Python variable.
**The Fix:** 
- **Do not use f-strings** for the main UI template. 
- Use placeholders and `.replace("__KEY__", value)` for dynamic data.
- If you MUST use an f-string, you must double every CSS/JS brace: `{{ ... }}`.

## 3. Broken Script Integrity
**Situation:** Accidentally deleting or moving a `</script>` tag during a large edit.
**The Bug:** The browser treats the trailing `</body>` and `</html>` and even Python return statements as part of the JavaScript code.
**The Fix:** Always verify that every opening `<script>` has a corresponding `</script>` precisely at the end of the logic block.

## 4. Backslash "Eating"
**Situation:** Using standard strings (`"""..."""`) for templates.
**The Bug:** Python converts escape sequences like `\t`, `\r`, and `\b` into whitespace/control characters before they reach the browser.
**The Fix:** Always prefix the template with `r`: `html = r"""..."""`.

## 5. View Visibility (Navigation Bug)
**Situation:** Setting `display: none` or using a CSS class that isn't applied correctly.
**The Bug:** The `setView(view)` function might run, but if the element's `display` property isn't explicitly toggled to `block`, the screen remains empty.
**The Fix:** Ensure the `setView` function explicitly sets `.style.display = 'block'` and `.style.visibility = 'visible'` for the target container.
