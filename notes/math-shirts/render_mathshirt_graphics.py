"""

Requires:
    pip install pylatex pypng toml pylatex

CommandLine:
    python ~/misc/facts/renderer.py print_facts
    python ~/misc/facts/renderer.py render_facts
"""
from pylatex import Document, NoEscape, Center
from pylatex.package import Package
from pylatex.base_classes import Command
import ubelt as ub


def main():
    # Create a new document
    doc = Document(documentclass='article')

    # Add necessary packages
    doc.packages.append(Package('amsmath'))
    doc.packages.append(Package('bm'))  # For bold math symbols
    doc.packages.append(Package('mathtools'))  # For :=
    doc.packages.append(Package('geometry', options=['margin=1in']))  # Safer margin setting

    doc.preamble.append(Command('pagestyle', 'empty'))
    # Increase font size for the equation
    # doc.preamble.append(Command('fontsize', '14pt', '18pt'))
    # doc.preamble.append(Command('selectfont'))

    # Define the content of the document
    # Add a centered environment
    with doc.create(Center()):
        # Add the SVD equation
        doc.append(NoEscape(ub.codeblock(
            r'''
            \begin{equation*}
                \mathbf{M}=
                \mathbf{U}\cdot
                \mathbf{\Sigma}\cdot
                \mathbf{V}^{*}
            \end{equation*}

            \vspace{1cm} % Add vertical space between equations

            % Epsilon-delta definition of limit
            \begin{equation*}
                \begin{gathered}
                \lim_{x \to p} f(x) = L \\
                \iff \\
                \forall \varepsilon > 0, \exists \delta > 0, \forall x, \\
                (|x - p| < \delta \Rightarrow |f(x) - L| < \varepsilon)
                \end{gathered}
            \end{equation*}

            \vspace{1cm} % Add vertical space between equations

            % Chain rule in Lagrange notation for h(x) = f(g(x))
            \begin{equation*}
                \begin{gathered}
                h(x) \coloneq f(g(x)) \Rightarrow \\
                h'(x) = f'(g(x)) \cdot g'(x)
                \end{gathered}
            \end{equation*}
            ''')))

    print(doc.dumps())

    # Generate the PDF
    doc.generate_pdf('svd_tshirt', clean_tex=False)

if __name__ == '__main__':
    """
    CommandLine:
        python ~/misc/notes/math-shirts/render_mathshirt_graphics.py
    """
    main()
