import os.path
from glob import glob
from datetime import datetime

from protocol import PlayerServerProtocol

class HttpServer:
    def __init__(self):
        self.sessions = {}
        self.types = {}
        self.types['.pdf'] = 'application/pdf'
        self.types['.jpg'] = 'image/jpeg'
        self.types['.txt'] = 'text/plain'
        self.types['.html'] = 'text/html'
        
        self.game_protocol = PlayerServerProtocol()

    def response(self, kode=404, message='Not Found', messagebody=b'', headers={}):
        tanggal = datetime.now().strftime('%c')
        resp = []
        resp.append(f"HTTP/1.0 {kode} {message}\r\n")
        resp.append(f"Date: {tanggal}\r\n")
        resp.append("Connection: close\r\n")
        resp.append("Server: myserver/1.0\r\n")
        resp.append(f"Content-Length: {len(messagebody)}\r\n")
        for kk in headers:
            resp.append(f"{kk}:{headers[kk]}\r\n")
        resp.append("\r\n")

        response_headers = "".join(resp)
        
        if not isinstance(messagebody, bytes):
            messagebody = messagebody.encode()

        return response_headers.encode() + messagebody

    def proses(self, data):
        requests = data.split("\r\n")
        baris = requests[0]
        all_headers = [n for n in requests[1:] if n]

        j = baris.split(" ")
        try:
            method = j[0].upper().strip()
            if method == 'GET':
                object_address = j[1].strip()
                return self.http_get(object_address, all_headers)
            elif method == 'POST':
                object_address = j[1].strip()
                return self.http_post(object_address, all_headers)
            else:
                return self.response(400, 'Bad Request', b'', {})
        except IndexError:
            return self.response(400, 'Bad Request', b'', {})

    def http_get(self, object_address, headers):
        if object_address.startswith('/game/'):
            command_parts = object_address.split('/')[2:]
            command_string = " ".join(command_parts)

            game_response_json = self.game_protocol.proses_string(command_string)
            
            return self.response(200, 'OK', game_response_json, {'Content-Type': 'application/json'})

        if object_address == '/':
            return self.response(200, 'OK', 'Ini Adalah web Server percobaan', {})
        if object_address == '/video':
            return self.response(302, 'Found', '', {'location': 'https://youtu.be/katoxpnTf04'})
        if object_address == '/santai':
            return self.response(200, 'OK', 'santai saja', {})

        object_address = object_address.strip('/')
        if not os.path.exists(object_address):
            return self.response(404, 'Not Found', '', {})
        
        with open(object_address, 'rb') as fp:
            isi = fp.read()
        
        fext = os.path.splitext(object_address)[1]
        content_type = self.types.get(fext, 'application/octet-stream')
        
        headers = {'Content-type': content_type}
        return self.response(200, 'OK', isi, headers)

    def http_post(self, object_address, headers):
        isi = "kosong"
        return self.response(200, 'OK', isi, {})
