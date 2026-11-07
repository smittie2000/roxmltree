"""Writes gen/g1..g9. g7-g9 are CRLF copies of files/14, 15 and 17, so run fetch first."""
from pathlib import Path

K = Path(__file__).resolve().parent
G = K / 'gen'
G.mkdir(exist_ok=True)
F = K / 'files'


def w(name, text):
    (G / name).write_bytes(text.encode('utf-8'))


w('g1-short-nonascii-text.xml', '<r>' + '<i>héllo</i>' * 100000 + '</r>')
w('g2-short-ascii-text.xml', '<r>' + '<i>hello</i>' * 100000 + '</r>')
w('g3-gt-text.xml', '<r>' + ('a > b; ' * 20 + '\n') * 3000 + '</r>')
w('g4-crlf-indented.xml', '<r>\r\n' + '    <c a="1"/>\r\n' * 50000 + '</r>')
w('g5-tab-attributes.xml', '<r>' + ('<a v="' + 'x' * 200 + '\t' + 'x' * 200 + '"/>') * 5000 + '</r>')
w('g6-short-attributes.xml', '<r>' + '<a a="1" b="22" c="333" d="x" e="yy"/>' * 20000 + '</r>')


def crlf(src, name):
    data = (F / src).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    (G / name).write_bytes(data)


crlf('14-catalina-points.kml', 'g7-crlf-kml.kml')
crlf('15-onvif.xsd', 'g8-crlf-onvif.xsd')
crlf('17-XMP.xmp', 'g9-crlf-xmp.xmp')
