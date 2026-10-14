from mdtoc import toc

DOC = """# Project

Intro.

## Install & Setup ##

```bash
# not a heading
## nor this
```

### Step 1: Download!

## Usage

#### Too deep

## Usage

~~~
# fenced
~~~

## Café `code` stuff
#NotAHeading
"""


def test_full_document():
    assert toc(DOC) == (
        "- [Project](#project)\n"
        "  - [Install & Setup](#install--setup)\n"
        "    - [Step 1: Download!](#step-1-download)\n"
        "  - [Usage](#usage)\n"
        "  - [Usage](#usage-1)\n"
        "  - [Café `code` stuff](#café-code-stuff)\n"
    )


def test_max_level_and_relative_indent():
    doc = "## A\n### B\n#### C\n## D\n"
    assert toc(doc, max_level=3) == "- [A](#a)\n  - [B](#b)\n- [D](#d)\n"
    assert toc(doc, max_level=4) == "- [A](#a)\n  - [B](#b)\n    - [C](#c)\n- [D](#d)\n"


def test_no_headings():
    assert toc("just text\n```\n# code\n```\n") == ""


def test_triple_duplicates_and_underscores():
    out = toc("# x_y\n# x_y\n# x_y\n")
    assert out == "- [x_y](#x_y)\n- [x_y](#x_y-1)\n- [x_y](#x_y-2)\n"
