# microtemplate -- task spec

Implement `render(template: str, context: dict) -> str` in `microtemplate/__init__.py`
so that **every test in `tests/` passes**. Run `python -m pytest tests/ -q`.

## Contract

1. **Literal text** passes through unchanged (including whitespace and newlines).
2. **`{{ var }}`** -> the value of `var` in `context`, coerced to `str`. Inner spaces optional
   (`{{var}}` == `{{ var }}`). Unknown variable -> empty string.
3. **Dotted paths** `{{ a.b.c }}` -> nested dict lookup. Any missing link -> empty string.
4. **HTML-escaped by default**: `&`->`&amp;`, `<`->`&lt;`, `>`->`&gt;`, `"`->`&quot;`, `'`->`&#x27;`.
5. **Raw (unescaped)** with triple braces: `{{{ var }}}`.
6. **`{{#if cond}}...{{/if}}`** renders the body only when `cond` is truthy (Python truthiness;
   missing -> falsy). Supports **`{{else}}`**.
7. **`{{#each items}}...{{/each}}`** repeats the body for each element. Inside, **`{{ this }}`** is
   the current element and **`{{ this.field }}`** accesses its fields. Empty/missing -> nothing.
   Items are escaped like normal variables.
8. **Nesting**: `if`/`each` blocks nest arbitrarily and interleave with literal text.

Do not modify `tests/`. Passing the full suite is the definition of done.
