import sys, glob; sys.path.insert(0,"/home/egg/Projects/Translate_Tool")
import docx
from app.backend.processors.docx_processor import _collect_docx_segments, _txbx_iter_texts
for f in sorted(glob.glob("/home/egg/Projects/Translate_Tool/docs/TEST_DOC/*.docx")):
    d=docx.Document(f)
    segs=_collect_docx_segments(d)
    para_cell_chars=sum(len(s.text) for s in segs if s.kind in ("para","cell"))
    txbx_chars=sum(len(t) for _,t in _txbx_iter_texts(d))
    n_para=sum(1 for s in segs if s.kind=="para")
    name=f.rsplit("/",1)[1][:30]
    print(f"{name:32s} para/cell_chars={para_cell_chars:6d} para_segs={n_para:3d} txbx_chars={txbx_chars}")
