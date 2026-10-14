// Pandoc Typst template for paper/paper.pdf (built by paper/build_paper.py).
//
// Single column, Libertinus Serif, numbered sections, captions above tables, IEEE-style numeric
// references (pandoc --citeproc with paper/ieee.csl). The fonts named here ship inside the typst
// wheel, so the build does not depend on fonts installed on the machine. Nothing in this file is
// prose: every number in the paper comes from generated results via paper/main.md.

#set document(
  title: [$title$],
  author: ($for(author)$"$author$"$sep$, $endfor$),
)

#set page(
  paper: "a4",
  margin: (top: 2.4cm, bottom: 2.4cm, left: 2.3cm, right: 2.3cm),
  numbering: "1",
  number-align: center,
  header: context {
    if counter(page).get().first() > 1 [
      #set text(size: 7.5pt, fill: luma(110))
      #align(center)[$if(running-title)$$running-title$$else$$title$$endif$]
    ]
  },
)

#set text(font: "Libertinus Serif", size: 10pt, lang: "en", region: "GB")
#set par(justify: true, leading: 0.58em, spacing: 0.85em, first-line-indent: 0pt)
#set heading(numbering: "1.1")
#set list(indent: 0.8em, spacing: 0.55em)
#set enum(indent: 0.8em, spacing: 0.55em)
#set footnote.entry(separator: line(length: 25%, stroke: 0.4pt + luma(140)))

#show heading.where(level: 1): it => block(above: 1.7em, below: 0.75em)[
  #set text(size: 13pt, weight: "bold")
  #it
]
#show heading.where(level: 2): it => block(above: 1.35em, below: 0.6em)[
  #set text(size: 11pt, weight: "bold")
  #it
]
#show heading.where(level: 3): it => block(above: 1.1em, below: 0.5em)[
  #set text(size: 10pt, weight: "semibold", style: "italic")
  #it
]

#show raw: set text(font: "DejaVu Sans Mono", size: 8.3pt)
#show raw.where(block: true): it => block(width: 100%, fill: luma(247), inset: 7pt, radius: 2pt, it)

#show link: set text(fill: rgb("#1f3f73"))
#show quote: set block(inset: (left: 1.2em, right: 1.2em), above: 0.9em, below: 0.9em)
#show quote: set text(size: 9.2pt)

// Tables: header rule, light rules between rows, no vertical rules; long tables may break.
#show figure.where(kind: table): set figure.caption(position: top)
#show figure.where(kind: table): set block(breakable: true)
#show figure.caption: set text(size: 8.6pt)
#set table(
  inset: (x: 4pt, y: 3.5pt),
  align: left + horizon,
  stroke: (x, y) => (bottom: if y == 0 { 0.6pt + black } else { 0.3pt + luma(200) }),
)
#show table.cell.where(y: 0): set text(weight: "semibold", size: 7.8pt)
#show table.cell: set text(size: 7.8pt)
#show table.cell: set align(left)
#show table.cell: it => {
  show raw: set text(size: 7pt)
  it
}
#show table: set par(justify: false)

// Figures: centred, caption below, kept whole.
#show figure.where(kind: image): set figure.caption(position: bottom)
#show figure.where(kind: image): set block(breakable: false)
#show image: it => align(center, it)

#show <refs>: set text(size: 8.8pt)

$if(header-includes)$
$header-includes$
$endif$

#align(center)[
  #block(width: 92%)[
    #set par(justify: false, leading: 0.5em)
    #text(size: 16.5pt, weight: "bold")[$title$]
  ]
  $if(subtitle)$
  #v(0.4em)
  #block(width: 88%)[#text(size: 11pt, style: "italic")[$subtitle$]]
  $endif$
  #v(0.9em)
  #text(size: 11pt)[$for(author)$$author$$sep$, $endfor$]
  $if(date)$
  #v(0.2em)
  #text(size: 9pt, fill: luma(110))[$date$ · github.com/thanatchon36/rulewarden]
  $endif$
]
#v(1.3em)

$if(abstract)$
#block(inset: (x: 1.6em))[
  #set text(size: 9.4pt)
  #set par(justify: true)
  #text(weight: "bold")[Abstract]
  #h(0.7em)
  $abstract$
]
#v(1.0em)
$endif$

$if(keywords)$
#block(inset: (x: 1.6em))[
  #set text(size: 8.8pt, fill: luma(70))
  #text(weight: "semibold")[Keywords] #h(0.6em) $for(keywords)$$keywords$$sep$ · $endfor$
]
#v(1.0em)
$endif$

$body$

$for(include-after)$
$include-after$
$endfor$
