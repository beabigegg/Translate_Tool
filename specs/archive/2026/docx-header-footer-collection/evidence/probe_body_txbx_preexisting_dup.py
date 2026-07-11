import sys; sys.path.insert(0,"/home/egg/Projects/Translate_Tool")
import docx
from lxml import etree
from app.backend.processors.docx_processor import _collect_docx_segments, _txbx_iter_texts
d=docx.Document()
p=d.add_paragraph("BODY_PLAIN")
xml='''<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:pict><v:shape xmlns:v="urn:schemas-microsoft-com:vml"><v:textbox><w:txbxContent>
   <w:p><w:r><w:t>BODY_TEXTBOX_TEXT</w:t></w:r></w:p>
 </w:txbxContent></v:textbox></v:shape></w:pict></w:r>'''
p._p.append(etree.fromstring(xml))
segs=_collect_docx_segments(d)
para_hits=[s.text for s in segs if s.kind=="para" and "BODY_TEXTBOX_TEXT" in s.text]
txbx_texts=[t for _,t in _txbx_iter_texts(d) if "BODY_TEXTBOX_TEXT" in t]
print("para segments containing textbox text:", para_hits)
print("_txbx_iter_texts yielding textbox text:", txbx_texts)
print("=> body ALREADY double-counts textbox text:" , bool(para_hits) and bool(txbx_texts))
