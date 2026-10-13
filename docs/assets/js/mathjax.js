window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex",
  },
};

if (window.document$ && typeof window.document$.subscribe === "function") {
  window.document$.subscribe(() => {
    if (window.MathJax.typesetPromise) window.MathJax.typesetPromise();
  });
}
