from socket import *
import socket
import threading
import logging

from http_handler import HttpServer

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

httpserver = HttpServer()

class ProcessTheClient(threading.Thread):
    def __init__(self, connection, address):
        self.connection = connection
        self.address = address
        threading.Thread.__init__(self)

    def run(self):
        rcv = ""
        while True:
            try:
                data = self.connection.recv(1024)
                if data:
                    d = data.decode('utf-8')
                    rcv += d
                    
                    if rcv.endswith('\r\n\r\n'):
                        logging.warning(f"Data from client {self.address}: {rcv.strip()}")
                        
                        hasil = httpserver.proses(rcv)
                        
                        logging.warning(f"Response to client {self.address}: OK")
                        self.connection.sendall(hasil)
                        break
                else:
                    break
            except Exception as e:
                logging.error(f"Error with client {self.address}: {e}")
                break
        self.connection.close()

class Server(threading.Thread):
    def __init__(self, port=8889):
        self.the_clients = []
        self.port = port
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        threading.Thread.__init__(self)

    def run(self):
        self.my_socket.bind(('0.0.0.0', self.port))
        self.my_socket.listen(5)
        logging.warning(f"Server running on port {self.port}...")
        
        while True:
            try:
                connection, client_address = self.my_socket.accept()
                logging.warning(f"Connection from {client_address}")
                clt = ProcessTheClient(connection, client_address)
                clt.start()
                self.the_clients.append(clt)
            except Exception as e:
                logging.error(f"Server error: {e}")
                break

def main():
    svr = Server(port=8889)
    svr.start()

if __name__ == "__main__":
    main()
