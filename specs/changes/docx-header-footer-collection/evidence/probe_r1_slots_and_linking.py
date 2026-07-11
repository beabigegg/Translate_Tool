import sys; sys.path.insert(0,"/home/egg/Projects/Translate_Tool")
import docx
d=docx.Document()
sec=d.sections[0]
slots=[("header",sec.header),("first_page_header",sec.first_page_header),
       ("even_page_header",sec.even_page_header),("footer",sec.footer),
       ("first_page_footer",sec.first_page_footer),("even_page_footer",sec.even_page_footer)]
for name,part in slots:
    el=part._element
    print(f"{name:18s} _element.tag={el.tag.split('}')[-1]:4s} has_is_linked={hasattr(part,'is_linked_to_previous')} linked={part.is_linked_to_previous} has_paragraphs={hasattr(part,'paragraphs')} has_tables={hasattr(part,'tables')}")
# linked sharing: add a 2nd section, header linked -> same element?
from docx.enum.section import WD_SECTION
d.add_section(WD_SECTION.NEW_PAGE)
s2=d.sections[1]
print("2nd section header linked_to_prev:", s2.header.is_linked_to_previous)
print("  same _element as section0 header?:", s2.header._element is sec.header._element)
