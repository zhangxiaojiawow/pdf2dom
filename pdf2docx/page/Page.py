# -*- coding: utf-8 -*-

'''Page object parsed with PDF raw dict.

In addition to base structure described in :py:class:`~pdf2docx.page.RawPage`, 
some new features, e.g. sections, table block, are also included. 
Page elements structure:

* :py:class:`~pdf2docx.page.Page` >> :py:class:`~pdf2docx.layout.Section` >> :py:class:`~pdf2docx.layout.Column`  
    * :py:class:`~pdf2docx.layout.Blocks`
        * :py:class:`~pdf2docx.text.TextBlock` >> 
          :py:class:`~pdf2docx.text.Line` >> 
          :py:class:`~pdf2docx.text.TextSpan` / :py:class:`~pdf2docx.image.ImageSpan` >>
          :py:class:`~pdf2docx.text.Char`
        * :py:class:`~pdf2docx.table.TableBlock` >>
          :py:class:`~pdf2docx.table.Row` >> 
          :py:class:`~pdf2docx.table.Cell`
            * :py:class:`~pdf2docx.layout.Blocks`
            * :py:class:`~pdf2docx.shape.Shapes`
    * :py:class:`~pdf2docx.shape.Shapes`
        * :py:class:`~pdf2docx.shape.Shape.Stroke`
        * :py:class:`~pdf2docx.shape.Shape.Fill`
        * :py:class:`~pdf2docx.shape.Shape.Hyperlink`

::

    {
        "id": 0, # page index
        "width" : w,
        "height": h,
        "margin": [left, right, top, bottom],
        "sections": [{
            ... # section properties
        }, ...],
        "floats": [{
            ... # floating picture
        }, ...]
    }

'''

from docx.shared import Pt
from docx.enum.section import WD_SECTION
from ..common.Collection import BaseCollection
from ..common.share import debug_plot
from .BasePage import BasePage
from ..layout.Sections import Sections
from ..image.ImageBlock import ImageBlock
from ..text.TextSpan import TextSpan


class Page(BasePage):
    '''Object representing the whole page, e.g. margins, sections.'''

    def __init__(self, id: int = -1,
                 skip_parsing: bool = True,
                 width: float = 0.0,
                 height: float = 0.0,
                 header: str = None,
                 footer: str = None,
                 margin: tuple = None,
                 sections: Sections = None,
                 float_images: BaseCollection = None):
        '''Initialize page layout.

        Args:
            id (int, optional): Page index. Defaults to -1.
            skip_parsing (bool, optional): Don't parse page if True. Defaults to True.
            width (float, optional): Page width. Defaults to 0.0.
            height (float, optional): Page height. Defaults to 0.0.
            header (str, optional): Page header. Defaults to None.
            footer (str, optional): Page footer. Defaults to None.
            margin (tuple, optional): Page margin. Defaults to None.
            sections (Sections, optional): Page contents. Defaults to None.
            float_images (BaseCollection, optional): Float images in th is page. Defaults to None.
        '''
        # page index
        self.id = id
        self.skip_parsing = skip_parsing

        # page size and margin
        super().__init__(width=width, height=height, margin=margin)

        # flow structure: 
        # Section -> Column -> Blocks -> TextBlock/TableBlock
        # TableBlock -> Row -> Cell -> Blocks
        self.sections = sections or Sections(parent=self)

        # page header, footer
        self.header = header or ''
        self.footer = footer or ''

        # floating images are separate node under page
        self.float_images = float_images or BaseCollection()

        self._finalized = False

    @property
    def finalized(self):
        return self._finalized

    def store(self):
        '''Store parsed layout in dict format.'''
        res = {
            'id': self.id,
            'width': self.width,
            'height': self.height,
            'margin': self.margin,
            'sections': self.sections.store(),
            'header': self.header,
            'footer': self.footer,
            'floats': self.float_images.store()
        }
        return res

    def restore(self, data: dict):
        '''Restore Layout from parsed results.'''
        # page id
        self.id = data.get('id', -1)

        # page width/height
        self.width = data.get('width', 0.0)
        self.height = data.get('height', 0.0)
        self.margin = data.get('margin', (0,) * 4)

        # parsed layout
        self.sections.restore(data.get('sections', []))
        self.header = data.get('header', '')
        self.footer = data.get('footer', '')

        # float images
        self._restore_float_images(data.get('floats', []))

        # Suppose layout is finalized when restored; otherwise, set False explicitly
        # out of this method.
        self._finalized = True

        return self

    @debug_plot('Final Layout')
    def parse(self, **settings):
        '''Parse page layout.'''
        self.sections.parse(**settings)
        self._finalized = True
        return self.sections  # for debug plot

    def extract_tables(self, **settings):
        '''Extract content from tables (top layout only).
        
        .. note::
            Before running this method, the page layout must be either parsed from source 
            page or restored from parsed data.
        '''
        # table blocks
        collections = []
        for section in self.sections:
            for column in section:
                if settings['extract_stream_table']:
                    collections.extend(column.blocks.table_blocks)
                else:
                    collections.extend(column.blocks.lattice_table_blocks)

        # check table
        tables = []  # type: list[ list[list[str]] ]
        for table_block in collections:
            tables.append(table_block.text)

        return tables

    def make_docx(self, doc):
        '''Set page size, margin, and create page. 

        .. note::
            Before running this method, the page layout must be either parsed from source 
            page or restored from parsed data.
        
        Args:
            doc (Document): ``python-docx`` document object
        '''
        # new page
        if doc.paragraphs:
            section = doc.add_section(WD_SECTION.NEW_PAGE)
        else:
            section = doc.sections[0]  # a default section is there when opening docx

        # page size
        section.page_width = Pt(self.width)
        section.page_height = Pt(self.height)

        # page margin
        left, right, top, bottom = self.margin
        section.left_margin = Pt(left)
        section.right_margin = Pt(right)
        section.top_margin = Pt(top)
        section.bottom_margin = Pt(bottom)

        # create flow layout: sections
        self.sections.make_docx(doc)

    def _restore_float_images(self, raws: list):
        '''Restore float images.'''
        self.float_images.reset()
        for raw in raws:
            image = ImageBlock(raw)
            image.set_float_image_block()
            self.float_images.append(image)

    def is_continuous_with_page(self, nextPage):
        """Check if the next page is continuous with this page."""
        # get the last no-footer block of this page
        cur_page_blocks = [block for section in self.sections for column in section
                           for block in column.blocks
                           if block.is_text_block and not (block.is_footer or block.is_header)]
        last_block_current_page = cur_page_blocks[-1] if cur_page_blocks else None
        next_page_blocks = [block for section in nextPage.sections for column in section
                            for block in column.blocks
                            if block.is_text_block and not (block.is_footer or block.is_header)]
        first_block_next_page = next_page_blocks[0] if next_page_blocks else None
        if (last_block_current_page is not None and
                last_block_current_page.lines.last_line_is_end_pargraph(line_break_free_space_ratio=0.1)):
            return False
        elif (last_block_current_page is not None and
              last_block_current_page.lines.last_line_is_end_sentence()):
            # 判断下一页的第一个block是否是开头, 如果是， 则两个不相临
            if first_block_next_page is None:
                return False
            last_line_last_block = last_block_current_page.lines[-1]
            last_span = [span for span in last_line_last_block.spans if isinstance(span, TextSpan)][-1]
            first_span = [span for span in first_block_next_page.lines[0].spans if isinstance(span, TextSpan)][0]
            last_span_font, last_span_size = last_span.font, last_span.size
            first_span_font, first_span_size = first_span.font, first_span.size
            if (last_span_font != first_span_font or
                    max(last_span_size, first_span_size) / min(last_span_size, first_span_size) > 1.2):
                return False
            return True
        else:
            return True

    def plot(self, raw_page, first_block_color=None):
        return self.sections.plot(raw_page, first_block_color)
