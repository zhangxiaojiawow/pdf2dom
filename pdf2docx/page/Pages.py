# -*- coding: utf-8 -*-

'''Collection of :py:class:`~pdf2docx.page.Page` instances.'''

import logging
from collections import Counter

from .RawPageFactory import RawPageFactory
from ..common.Collection import BaseCollection
from ..font.Fonts import Fonts
import re


class Pages(BaseCollection):
    '''A collection of ``Page``.'''

    def parse(self, fitz_doc, **settings):
        '''Analyze document structure, e.g. page section, header, footer.

        Args:
            fitz_doc (fitz.Document): ``PyMuPDF`` Document instance.
            settings (dict): Parsing parameters.
        '''
        # ---------------------------------------------
        # 0. extract fonts properties, especially line height ratio
        # ---------------------------------------------
        fonts = Fonts.extract(fitz_doc)

        # ---------------------------------------------
        # 1. extract and then clean up raw page
        # ---------------------------------------------
        pages, raw_pages = [], []
        words_found = False
        for page in self:
            if page.skip_parsing: continue

            # init and extract data from PDF
            raw_page = RawPageFactory.create(page_engine=fitz_doc[page.id], backend='PyMuPDF')
            raw_page.restore(**settings)

            # check if any words are extracted since scanned pdf may be directed
            if not words_found and raw_page.raw_text.strip():
                words_found = True

            # process blocks and shapes based on bbox
            raw_page.clean_up(**settings)

            # process font properties
            raw_page.process_font(fonts)            

            # after this step, we can get some basic properties
            # NOTE: floating images are detected when cleaning up blocks, so collect them here
            page.width = raw_page.width
            page.height = raw_page.height
            page.float_images.reset().extend(raw_page.blocks.floating_image_blocks)

            raw_pages.append(raw_page)
            pages.append(page)

        # show message if no words found
        if not words_found:
            logging.warning('Words count: 0. It might be a scanned pdf, which is not supported yet.')

        
        # ---------------------------------------------
        # 2. parse structure in document/pages level
        # ---------------------------------------------
        # NOTE: blocks structure might be changed in this step, e.g. promote page header/footer,
        # so blocks structure based process, e.g. calculating margin, parse section should be 
        # run after this step.
        header, footer = Pages._parse_document(raw_pages)


        # ---------------------------------------------
        # 3. parse structure in page level, e.g. page margin, section
        # ---------------------------------------------
        # parse sections
        for page, raw_page in zip(pages, raw_pages):
            # page margin
            margin = raw_page.calculate_margin(**settings)
            raw_page.margin = page.margin = margin

            # page section
            sections = raw_page.parse_section(**settings)
            page.sections.extend(sections)
    

    @staticmethod
    def _parse_document(raw_pages:list):
        '''Parse structure in document/pages level, e.g. header, footer'''
        # TODO
        return '', ''

    def extract_header_footer(self, **settings):
        header_blocks = []
        footer_blocks = []
        for page in self:
            if not page.finalized: continue
            header_section = page.sections[0] if len(page.sections) > 1 else []
            footer_section = page.sections[-1] if len(page.sections) > 1 else []
            header_blocks.append([column.blocks[0] for column in header_section])
            footer_blocks.append([column.blocks[-1] for column in footer_section])

        first_column_header = [blocks[0] for blocks in header_blocks if blocks]
        second_column_header = [blocks[1] for blocks in header_blocks if len(blocks) > 1]
        self.mark_header_footer_block(first_column_header, header=True)
        self.mark_header_footer_block(second_column_header, header=True)
        first_column_footer = [blocks[0] for blocks in footer_blocks if blocks]
        second_column_footer = [blocks[1] for blocks in footer_blocks if len(blocks) > 1]
        self.mark_header_footer_block(first_column_footer, header=False)
        self.mark_header_footer_block(second_column_footer, header=False)


    def mark_header_footer_block(self, blocks, header=False):
        if not blocks: return
        text_list = []
        for block in blocks:
            if block.is_text_block:
                text_list.append(block.text)
            elif block.is_table_block:
                text_list.append("".join(["".join(row) for row in block.text]))
            elif block.is_image_block:
                text_list.append("image")
            else:
                pass
        # 分析text_list规律
        remove_number_text = [self.remove_number(text) for text in text_list]
        text_counter = Counter(remove_number_text)
        # 如果出现次数最多的文本，出现的次数大于总文本的一半，那么就认为是页眉页脚
        if text_counter.most_common(1)[0][1] > len(remove_number_text) / 2:
            most_common_text = text_counter.most_common(1)[0][0]
            for block in blocks:
                if block.is_text_block:
                    if self.remove_number(block.text) == most_common_text:
                        block.mark_header() if header else block.mark_footer()
                elif block.is_table_block:
                    if self.remove_number("".join(["".join(row) for row in block.text])) == most_common_text:
                        block.mark_header() if header else block.mark_footer()
                elif block.is_image_block:
                    block.mark_header() if header else block.mark_footer()
                else:
                    pass

    def remove_number(self, text):
        # 在页眉，页脚，经常出现次序编号，首先将这些编号去掉,通过剩余文本的相似度，分析是否是页眉页脚
        pattern = r'[(一|二|三|四|五|六|七|八|九|十)万]?[(一|二|三|四|五|六|七|八|九)千]?[(一|二|三|四|五|六|七|八|九)百]?[(一|二|三|四|五|六|七|八|九)十]?[(一|二|三|四|五|六|七|八|九)]?'
        # 使用正则表达式，替换符合pattern中的字符为空
        text = re.sub(pattern, '', text)
        # 替换所有的数字为空
        text = re.sub(r'\d+', '', text)
        return text.strip()




