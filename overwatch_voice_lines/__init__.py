"""Download and prepare Overwatch hero voice lines for voice cloning.

The public entry point is :func:`overwatch_voice_lines.cli.main`; the package is
also usable as a library::

    from overwatch_voice_lines.api import WikiClient
    from overwatch_voice_lines.wikitext import parse_page

    page = WikiClient().fetch_page("Widowmaker/Quotes")
    result = parse_page(page.wikitext, page=page.title, character="Widowmaker")
"""

__version__ = "0.1.0"
