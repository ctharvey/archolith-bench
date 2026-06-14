"""Acceptance suite for microtemplate. The agent's goal: make ALL of these pass.

This is the objective done-criterion. The agent may read these tests; passing the
full suite == the feature is correct. Do not modify this file.
"""

import pytest
from microtemplate import render


# --- 1. literal passthrough ---------------------------------------------------

def test_plain_text_unchanged():
    assert render("hello world", {}) == "hello world"

def test_empty_template():
    assert render("", {}) == ""


# --- 2. variable substitution -------------------------------------------------

def test_simple_var():
    assert render("Hi {{ name }}!", {"name": "Ada"}) == "Hi Ada!"

def test_var_no_inner_spaces():
    assert render("{{name}}", {"name": "Ada"}) == "Ada"

def test_multiple_vars():
    assert render("{{a}}-{{b}}-{{a}}", {"a": "x", "b": "y"}) == "x-y-x"

def test_unknown_var_renders_empty():
    assert render("[{{missing}}]", {}) == "[]"

def test_non_string_var_coerced():
    assert render("n={{n}}", {"n": 42}) == "n=42"


# --- 3. dotted path access ----------------------------------------------------

def test_dotted_path():
    assert render("{{ user.name }}", {"user": {"name": "Bo"}}) == "Bo"

def test_deep_dotted_path():
    assert render("{{a.b.c}}", {"a": {"b": {"c": "deep"}}}) == "deep"

def test_dotted_missing_renders_empty():
    assert render("[{{a.b.c}}]", {"a": {}}) == "[]"


# --- 4. HTML escaping (default) + raw ----------------------------------------

def test_html_escaped_by_default():
    assert render("{{ x }}", {"x": "<b>&\"'"}) == "&lt;b&gt;&amp;&quot;&#x27;"

def test_triple_brace_is_raw():
    assert render("{{{ x }}}", {"x": "<b>"}) == "<b>"


# --- 5. {{#if}} ---------------------------------------------------------------

def test_if_truthy():
    assert render("{{#if show}}YES{{/if}}", {"show": True}) == "YES"

def test_if_falsy_omitted():
    assert render("{{#if show}}YES{{/if}}", {"show": False}) == ""

def test_if_missing_is_falsy():
    assert render("{{#if nope}}X{{/if}}", {}) == ""

def test_if_empty_list_is_falsy():
    assert render("{{#if items}}X{{/if}}", {"items": []}) == ""

def test_if_else_true_branch():
    assert render("{{#if v}}A{{else}}B{{/if}}", {"v": True}) == "A"

def test_if_else_false_branch():
    assert render("{{#if v}}A{{else}}B{{/if}}", {"v": 0}) == "B"


# --- 6. {{#each}} -------------------------------------------------------------

def test_each_scalars_with_this():
    assert render("{{#each xs}}[{{this}}]{{/each}}", {"xs": [1, 2, 3]}) == "[1][2][3]"

def test_each_dicts_field():
    ctx = {"users": [{"name": "A"}, {"name": "B"}]}
    assert render("{{#each users}}{{this.name}};{{/each}}", ctx) == "A;B;"

def test_each_empty_renders_nothing():
    assert render("x{{#each xs}}{{this}}{{/each}}y", {"xs": []}) == "xy"

def test_each_escapes_items():
    assert render("{{#each xs}}{{this}}{{/each}}", {"xs": ["<", ">"]}) == "&lt;&gt;"


# --- 7. nesting + interleaving ------------------------------------------------

def test_nested_each_in_if():
    ctx = {"on": True, "xs": ["a", "b"]}
    assert render("{{#if on}}{{#each xs}}{{this}}{{/each}}{{/if}}", ctx) == "ab"

def test_nested_if_in_each():
    ctx = {"xs": [{"v": True, "n": "y"}, {"v": False, "n": "n"}]}
    out = render("{{#each xs}}{{#if this.v}}{{this.n}}{{/if}}{{/each}}", ctx)
    assert out == "y"

def test_text_around_blocks_preserved():
    ctx = {"name": "Ada", "items": ["x", "y"]}
    tmpl = "Hi {{name}}. Items: {{#each items}}<{{this}}>{{/each}}. Done."
    assert render(tmpl, ctx) == "Hi Ada. Items: <x><y>. Done."

def test_whitespace_and_newlines_preserved():
    assert render("a\n{{v}}\nb", {"v": "MID"}) == "a\nMID\nb"
