import sys; sys.path.insert(0,"/home/egg/Projects/Translate_Tool")
import docx
from lxml import etree
from app.backend.processors.docx_processor import _p_text_with_breaks
d=docx.Document()
p=d.sections[0].header.paragraphs[0]
p.text="HDR_PLAIN_TEXT"
xml='''<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:pict><v:shape xmlns:v="urn:schemas-microsoft-com:vml"><v:textbox><w:txbxContent>
   <w:p><w:r><w:t>TEXTBOX_IN_HEADER</w:t></w:r></w:p>
 </w:txbxContent></v:textbox></v:shape></w:pict></w:r>'''
p._p.append(etree.fromstring(xml))
extracted=_p_text_with_breaks(p)
print("_p_text_with_breaks:", repr(extracted))
print("OVERLAP HAZARD (native would grab textbox text COM also does):", "TEXTBOX_IN_HEADER" in extracted)
