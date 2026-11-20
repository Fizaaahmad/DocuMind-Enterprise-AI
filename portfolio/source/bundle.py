"""Bundle canonical assets; exclude extracted archives, previews and bytecode."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from assets import SCREENSHOTS, VERIFICATION_FILES
root=Path(__file__).resolve().parents[1]
target=root/'DocuMind-Portfolio-Package.zip'
with ZipFile(target,'w',compression=ZIP_DEFLATED,compresslevel=6) as archive:
    for path in sorted(root.rglob('*')):
        relative=path.relative_to(root)
        if not path.is_file() or path==target:
            continue
        if relative.parts[0]=='DocuMind-Portfolio-Package':
            continue
        if relative.parts[0]=='verification' and path.suffix.lower()=='.png':
            continue
        if relative.parts[0]=='verification' and relative.as_posix() not in VERIFICATION_FILES:
            continue
        if relative.parts[0]=='screenshots' and relative.as_posix() not in SCREENSHOTS:
            continue
        if relative.parts[0]=='source' and (path.suffix=='.html' or 'demo-documents' in relative.parts):
            continue
        if '__pycache__' in relative.parts or path.suffix=='.pyc':
            continue
        archive.write(path,Path('DocuMind-Portfolio')/relative)
with ZipFile(target) as archive:
    assert archive.testzip() is None
print(f'Complete portfolio archive: {target.name} ({target.stat().st_size/1024/1024:.1f} MiB)')
