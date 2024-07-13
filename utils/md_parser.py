"""Custom audio element
Parses markdown of the form ![audio:src.mp3] and renders an audio element
"""

from marko import Markdown
from marko.helpers import MarkoExtension
from marko.inline import InlineElement

class AudioElement(InlineElement):
    pattern = r'\!\[audio\:(?P<src>.+?)\]'
    parse_children = False

    def __init__(self, match):
        self.target = match.group('src')


class AudioElementMixin:
    def render_audio_element(self, element):
        return f'<audio src="{element.target}" controls></audio>'


Audio = MarkoExtension(
    elements=[AudioElement],
    renderer_mixins=[AudioElementMixin])

markdown_parser = Markdown(extensions=[Audio])
