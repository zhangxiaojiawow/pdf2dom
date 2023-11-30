# -*- coding: utf-8 -*-

'''Column of Section.

In most cases, one section per page. But in case multi-columns page, sections are used 
to distinguish these different layouts.

.. note::
    Currently, support at most two columns.

::

    {
        'bbox': (x0, y0, x1, y1),
        'blocks': [{
            ... # block instances
        }, ...],
        'shapes': [{
            ... # shape instances
        }, ...]
    }
'''

from ..common.Collection import Collection
from ..common.Element import Element
from ..layout.Layout import Layout
from ..shape.Shape import Shape
from ..text.Line import Line
from ..text.TextSpan import TextSpan


class Column(Element, Layout):

    def is_agjacent_with(self, other, **kwargs):
        """Check if current column is adjacent with other column."""
        left_blocks = [block for block in self.blocks if block.is_text_block]
        last_left = left_blocks[-1] if left_blocks else None
        right_blocks = [block for block in other.blocks if block.is_text_block]
        first_right = right_blocks[0] if right_blocks else None
        if last_left is None or first_right is None:
            return False
        left_spans = [span for span in last_left.lines[-1].spans if isinstance(span, TextSpan)]
        left_font = left_spans[-1].font if left_spans else None
        right_spans = [span for span in first_right.lines[0].spans if isinstance(span, TextSpan)]
        right_font = right_spans[0].font if right_spans else None
        left_size = left_spans[-1].size if left_spans else None
        right_size = right_spans[0].size if right_spans else None

        if last_left.lines.last_line_is_end_pargraph(kwargs['line_break_free_space_ratio']):
            return False
        elif last_left.lines.last_line_is_end_sentence() and \
                (left_font != right_font or max(left_size, right_size) / min(left_size, right_size) > 1.2):
            return False
        else:
            return True

    def __init__(self, blocks=None, shapes=None):
        '''Initialize empty column.'''
        # Call the first parent class constructor only if omitting constructor. 
        # Unified constructor should be used (with *args, **kwargs) if using super().__init__().
        Element.__init__(self)
        Layout.__init__(self, blocks, shapes)


    @property
    def working_bbox(self): return self.bbox


    def add_elements(self, elements:Collection):
        '''Add candidate elements, i.e. lines or shapes, to current column.'''
        blocks = [e for e in elements if isinstance(e, Line)]
        shapes = [e for e in elements if isinstance(e, Shape)]
        self.assign_blocks(blocks)
        self.assign_shapes(shapes)


    def store(self):
        '''Store parsed section layout in dict format.'''
        res = Element.store(self)
        res.update(Layout.store(self))
        return res


    def restore(self, raw:dict):
        '''Restore Column from raw dict.'''
        self.update_bbox(raw.get('bbox', (0,)*4))
        super().restore(raw)
        return self


    def make_docx(self, doc):
        '''Create Section Column in docx. 

        Args:
            doc (Document): ``python-docx`` document object
        '''
        self.blocks.make_docx(doc)



