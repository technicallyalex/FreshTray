"""Bounded raster logo normalization shared by local and provider imports."""
import base64
from PySide6.QtCore import QBuffer,QByteArray,QIODevice,Qt
from PySide6.QtGui import QImageReader

def normalized_logo(data):
    if len(data)>10*1024*1024:raise ValueError('Choose a logo smaller than 10 MB.')
    source=QBuffer();source.setData(QByteArray(data));source.open(QIODevice.ReadOnly)
    reader=QImageReader(source);reader.setAutoTransform(True);size=reader.size()
    if not size.isValid() or size.width()*size.height()>24000000:raise ValueError('Choose a PNG or JPEG logo below 24 megapixels.')
    image=reader.read()
    if image.isNull():raise ValueError('This logo could not be opened.')
    image=image.scaled(800,400,Qt.KeepAspectRatio,Qt.SmoothTransformation)
    encoded=QByteArray();buffer=QBuffer(encoded);buffer.open(QIODevice.WriteOnly)
    if not image.save(buffer,'PNG'):raise ValueError('Could not save the logo.')
    return 'data:image/png;base64,'+base64.b64encode(bytes(encoded)).decode('ascii')
