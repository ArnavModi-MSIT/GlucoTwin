"""Fetch CSV/notebook members from the official archive without meal photos."""
import concurrent.futures, io, json, pathlib, struct, urllib.request, zipfile, zlib

URL = 'https://physionet-open.s3.amazonaws.com/cgmacros/1.0.0/CGMacros_dateshifted365.zip'
SIZE = 657187340
ROOT = pathlib.Path(__file__).parent / 'data/raw/cgmacros'

def fetch(start, length):
    request = urllib.request.Request(URL, headers={'Range': f'bytes={start}-{start+length-1}'})
    with urllib.request.urlopen(request, timeout=90) as response:
        if response.status != 206:
            raise RuntimeError('Server did not honor range request')
        value = response.read()
    if len(value) != length:
        raise RuntimeError('Incomplete range')
    return value

class RemoteArchive(io.RawIOBase):
    def __init__(self): self.pos = 0
    def seekable(self): return True
    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else SIZE + offset
        return self.pos
    def tell(self): return self.pos
    def read(self, length=-1):
        length = SIZE-self.pos if length < 0 else min(length, SIZE-self.pos)
        if length <= 0: return b''
        value = fetch(self.pos, length)
        self.pos += len(value)
        return value

def download(info):
    target = (ROOT / info.filename).resolve()
    if not target.is_relative_to(ROOT.resolve()):
        raise RuntimeError('Unsafe archive path')
    if target.exists() and target.stat().st_size == info.file_size:
        if zlib.crc32(target.read_bytes()) == info.CRC:
            return 'verified ' + info.filename
    header = fetch(info.header_offset, 30)
    name_len, extra_len = struct.unpack_from('<HH', header, 26)
    payload = fetch(info.header_offset+30+name_len+extra_len, info.compress_size)
    if info.compress_type == zipfile.ZIP_DEFLATED:
        payload = zlib.decompress(payload, -15)
    elif info.compress_type != zipfile.ZIP_STORED:
        raise RuntimeError('Unsupported compression')
    if len(payload) != info.file_size or zlib.crc32(payload) != info.CRC:
        raise RuntimeError('Member integrity failure: ' + info.filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return 'downloaded ' + info.filename

if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(RemoteArchive()) as archive:
        infos = archive.infolist()
    selected = [i for i in infos if not i.is_dir() and '__MACOSX' not in i.filename and i.filename.lower().endswith(('.csv', '.ipynb', '.txt', '.md'))]
    (ROOT/'archive_inventory.json').write_text(json.dumps([{'path':i.filename,'bytes':i.file_size,'compressed_bytes':i.compress_size,'crc32':i.CRC} for i in infos], indent=2))
    print(f'Selected {len(selected)} members; compressed {sum(i.compress_size for i in selected)/2**20:.2f} MiB', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for result in pool.map(download, selected): print(result, flush=True)
    print('COMPLETE: all selected members passed ZIP CRC checks.', flush=True)
