"""Fetches the bench files from their original sources and checks them.

usage: python -I fetch.py <path to roxmltree clone>
Writes files/ (17 real files) and ds/ (dependents' files listed in ds-list.txt), then checks SHA-256.
The CSW file (09) is a live query, so its hash is expected to differ from the copy measured before.
"""
import hashlib
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

K = Path(__file__).resolve().parent
F = K / 'files'
F.mkdir(exist_ok=True)
repo = Path(sys.argv[1]).resolve()

BENCHES = ['attributes.xml', 'cdata.xml', 'fonts.conf', 'gigantic.svg', 'huge.xml', 'large.plist', 'medium.svg', 'text.xml']
RAW = 'https://raw.githubusercontent.com'
URLS = {
    '09-metadata.vlaanderen.be.xml': 'https://metadata.vlaanderen.be/srv/dut/csw?service=CSW&version=2.0.2&request=GetRecords'
        '&typeNames=gmd:MD_Metadata&outputSchema=http://www.isotc211.org/2005/gmd&elementSetName=full'
        '&resultType=results&maxRecords=38',
    '10-www.geonames.org_ontology_ontology_v3.3.rdf.rdf': 'https://www.geonames.org/ontology/ontology_v3.3.rdf',
    '11-slr-canon.xml': f'{RAW}/lensfun/lensfun/52cf1a7b0e82e07e0ecaa3391ee5106a6dd1ee54/data/db/slr-canon.xml',
    '12-fcla-xml-2.30li58.xhtml': f'{RAW}/IDPF/epub3-samples/7651e2002b631e6577fadf7e9e0692fa6efb8746/30/linear-algebra/EPUB/xhtml/fcla-xml-2.30li58.xhtml',
    '13-FT_G2G_TD01_con_Allegato,_Bonifico_e_Split_Payment.xml': f'{RAW}/ConnectingEurope/eInvoicing-EN16931/b17b2695e5e3e021945c38658326b78a76f80f84/ubl/examples/FT%20G2G_TD01%20con%20Allegato,%20Bonifico%20e%20Split%20Payment.xml',
    '14-catalina-points.kml': f'{RAW}/googlearchive/kml-samples/0ccb611310912a3c7aae0ddddfe41de60479a83a/gw10/catalina/catalina-points.kml',
    '15-onvif.xsd': f'{RAW}/onvif/specs/7dd791435c69944f6f18b9dd1e50ff189a442338/wsdl/ver10/schema/onvif.xsd',
    '16-embedded-16bit-png.svg': f'{RAW}/linebender/resvg/04291b740387ca7310bce66cd7108ee8d7c51ef0/crates/resvg/tests/tests/structure/image/embedded-16bit-png.svg',
    '17-XMP.xmp': f'{RAW}/exiftool/exiftool/9b8664dfcf2c609d3cc8925d380e98ad2a379f9b/t/images/XMP.xmp',
}
SHA = {
    '01-attributes.xml': 'dbed55157bc571e3759063c0a22676e2225214330f85845686835a391da463e7',
    '02-cdata.xml': '306b1f06a70df2c17cc554c3767431963a86fee274ec553c91829780b5f9cc04',
    '03-fonts.conf': 'd387387a6b93b66051135205c15ae223d3c0c1404cec840fa25f8bacfa381696',
    '04-gigantic.svg': '817220cb5af27dc5f1881a410862906a575c215227900b24f09bd439260e9af0',
    '05-huge.xml': '7c6140f8c96152882ab9bc45753a4b59d36fab5f1aa69038c10face55f02c1d3',
    '06-large.plist': 'd7614a4a7a1293549deb0b7c47fa85173f60e402c3bbc69acccf45c97faf5008',
    '07-medium.svg': '52f7dd3d4d20833539ba312a77f6f4f80ef0ca7ac1b457ecba08ada9ece62540',
    '08-text.xml': '57591f3576b7ba5ab8bc9412a1c86cdf4c0f15d52feed791ccde9adf503015a8',
    '09-metadata.vlaanderen.be.xml': 'a208e70b11b5df00daa5802db71c50209de247952b4e2439ebf76f877a48ee33',
    '10-www.geonames.org_ontology_ontology_v3.3.rdf.rdf': 'dcd85810b10623520567700e4c6ab560ab9e16bd7f53387b893beee238b9f50c',
    '11-slr-canon.xml': '5244e6df8f2522f829c57e2073313ce31a624e9ed9605310fe43613b9d588c99',
    '12-fcla-xml-2.30li58.xhtml': '793659ff04006b3d3847c2e4c3ce0e13ea0a4ceedc293ab5276d276e62aab48c',
    '13-FT_G2G_TD01_con_Allegato,_Bonifico_e_Split_Payment.xml': 'b789ae1942994ac2cf4aba8387023c36e815906e2938fafaabd2e052eede6806',
    '14-catalina-points.kml': 'dc45e11497c168b430e4fd4ced9dd0480b32838ad86b33722edb09ffcc6f17c8',
    '15-onvif.xsd': '3438bdb7bc203fa71420a993a4aed6112184d759e020f7b45b7555c824484904',
    '16-embedded-16bit-png.svg': '34103ec832ce3aab8b96bc17633799769147752faf3e5905a454d62da2176e16',
    '17-XMP.xmp': '3ed6ed1ce6a0c611f43e290c019e260e81d1fb85733963e108faa19927b01134',
}
DS_REPOS = {
    'resvg': ('https://github.com/linebender/resvg', '04291b740387ca7310bce66cd7108ee8d7c51ef0'),
    'fontconfig': ('https://gitlab.freedesktop.org/fontconfig/fontconfig.git', 'b6cf4b270c42b13347a4012cdceb9bbc3d2e8f32'),
    'fontconfig-parser': ('https://github.com/Riey/fontconfig-parser', 'b8a29fbb7fcf217b3cb74c0e77040e1d61a61922'),
    'mailrs': ('https://github.com/goliajp/mailrs', 'fa75c6a2f4e28aef8fc88678673a87bb63f6eabb'),
    'dioxus': ('https://github.com/DioxusLabs/dioxus', '7dfd07eb7a7ef130f49de043327e762e24cd484e'),
    'openvmm': ('https://github.com/microsoft/openvmm', '69cdd7f4e22c66fb508467f70b926fbfd821ec0b'),
}
DS_SHA = '05f66374261fffa9e9c4db1088a95a1433b357576ce40ddb29d116cb214b2dfc'


def sha(data):
    return hashlib.sha256(data).hexdigest()


for i, name in enumerate(BENCHES, 1):
    data = subprocess.run(['git', '-C', repo, 'show', f'origin/upstream-ready/base:benches/{name}'],
                          capture_output=True, check=True).stdout
    (F / f'{i:02}-{name}').write_bytes(data)
for name, url in URLS.items():
    req = urllib.request.Request(url, headers={'User-Agent': 'roxmltree-bench-kit'})
    with urllib.request.urlopen(req, timeout=120) as r:
        (F / name).write_bytes(r.read())
for name, want in SHA.items():
    got = sha((F / name).read_bytes())
    print(('ok  ' if got == want else 'DIFF') + f' {name}' + ('' if got == want else f' (got {got})'))

# Dependents: shallow-fetch each repository at its commit, copy the listed files.
src = K / 'repos'
src.mkdir(exist_ok=True)
for name, (url, commit) in DS_REPOS.items():
    d = src / name
    if not (d / '.git').exists():
        subprocess.run(['git', 'init', '-q', d], check=True)
        subprocess.run(['git', '-C', d, 'config', 'core.autocrlf', 'false'], check=True)
        subprocess.run(['git', '-C', d, 'remote', 'add', 'origin', url], check=True)
    subprocess.run(['git', '-C', d, 'fetch', '-q', '--depth', '1', 'origin', commit], check=True)
    subprocess.run(['git', '-C', d, 'checkout', '-q', '--force', 'FETCH_HEAD'], check=True)
ds = K / 'ds'
h = hashlib.sha256()
n = 0
for rel in (K / 'ds-list.txt').read_text(encoding='utf-8').splitlines():
    rel = rel.strip()
    if not rel:
        continue
    data = (src / rel).read_bytes()
    out = ds / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    h.update(rel.encode() + b'\0' + data)
    n += 1
print(f'ds: {n} files,', 'ok' if h.hexdigest() == DS_SHA else f'DIFF (got {h.hexdigest()})')
