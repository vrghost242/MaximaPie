import asyncio
import shutil
import socket
import queue
import threading
import time
from typing import Tuple, Callable, Optional
from logger import Logger
import re

is_max_prompt = re.compile(r"(%i1)")

class MaximaServer:
    def __init__(self,
                 port_range=(64000, 64100),
                 host: str = "localhost",
                 maxima_path: str = "maxima",
                 handler: Optional[Callable[[str], str]] = None
    ):

        self.log = Logger("MaximaServer")

        #Socket Server settings
        self.port_range = port_range
        self.host = host
        self.server_socket: Optional[socket.socket] = None
        self.server_thread: Optional[threading.Thread] = None
        self.server_running = False
        self.handler = handler or self._default_handler
        self.port = None

        #Maxima settings
        self.maxima_path = maxima_path
        self.maxima_instance = None
        self.maxima_status = None
        self.maxima_info = {
            "pid": None,
            "version": "N/A",
            "lisp_version": "N/A"
        }
        self._valid_maxima_path()

        #Communication Queue
        self.send_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self._clients: list[threading.Thread] = []

    def _default_handler(self, command: str) -> str:
        """Override this or pass a handler to __init__"""
        return f"Received: {command}"

    def _valid_maxima_path(self):
        """
        Validates the presence and accuracy of the configured Maxima executable path.

        This method checks if the Maxima executable exists at the assigned path and updates it if the
        executable is found in the system's PATH environment. If the executable cannot be found, it raises
        a FileNotFoundError and logs an error message. Upon successful verification, it logs the found
        location of the Maxima executable.

        :raises FileNotFoundError: If the Maxima executable cannot be located at the specified path.
        """
        if not shutil.which(self.maxima_path):
            self.log.error(f"Maxima not found at {self.maxima_path}")
            raise FileNotFoundError(f"Maxima not found at specified path. {self.maxima_path}")
        else:
            self.maxima_path = shutil.which(self.maxima_path)
            self.log.info(f"Maxima found at {self.maxima_path}")

    def _select_free_port(self, port_range, host):
        """
        Selects a free port within the specified range on the given host. If the port range contains
        only a single port, it checks the availability of that port. If the range contains two ports,
        it iterates through all ports in the range and selects the first available port. If no free
        ports are available within the range, the method logs an error and exits the program.

        :param port_range: The port range specified. Can be a single integer or a tuple of two integers
            representing the lower and upper bounds of the range (inclusive).
        :type port_range: Union[int, Tuple[int, int]]
        :param host: The name of the host on which to look for an available port.
        :type host: str
        :return: The first free port found in the range, or logs an error and exits the program if no
            free ports are found.
        :rtype: int
        """
        if isinstance(port_range, int):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((host, port_range))
                    return port_range
                except OSError:
                    self.log.error(f"Port {port_range[0]} is already in use")
                    exit(2)
        elif len(port_range) != 2:
            self.log.error("Invalid port range, need a start and a end port range")
            exit(2)
        elif isinstance(port_range[0], int) and isinstance(port_range[1], int):
            for port in range(port_range[0], port_range[1]):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    try:
                        s.bind((host, port))
                        return port
                    except OSError:
                        continue
            self.log.error(f"No free ports found in range: {port_range[0]}-{port_range[1]}")
            exit(2)
        else:
            self.log.error("Invalid port range, need a numerical start and a end port range")
            exit(2)

    def _handle_client(self, client_socket: socket.socket, address: tuple):
        """Handle a single client connection"""
        self.log.info(f"Connection from {address}")
        client_socket.settimeout(1.0)

        while self.server_running:
            try:
                data = client_socket.recv(4096)
                if not data:
                    break
                self.log.debug(f"Received: {data.decode('utf-8').strip()}")
                package = data.decode('utf-8').strip()


                command = data.decode('utf-8').strip()
                response = self.handler(command)

                # Store in queue for main thread to pick up
                self.response_queue.put({
                    'address': address,
                    'command': command,
                    'response': response
                })

                # Send response back to client
                # client_socket.send(response.encode('utf-8'))

            except socket.timeout:
                continue
            except (ConnectionResetError, BrokenPipeError):
                break

        client_socket.close()
        print(f"Connection closed: {address}")

    def _accept_loop(self):
        """Main loop accepting new connections"""
        while self.server_running:
            try:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()
                self._clients.append(client_thread)
            except socket.timeout:
                continue
            except OSError:
                break

    def get_response(self, block: bool = False, timeout: Optional[float] = None) -> Optional[dict]:
        """
        Get a response from the queue.

        block=False: Return immediately (None if empty)
        block=True: Wait until something is available
        timeout: Max seconds to wait (only if block=True)
        """
        try:
            return self.response_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def get_all_responses(self) -> list[dict]:
        """Get all pending responses without blocking"""
        results = []
        while True:
            item = self.get_response(block=False)
            if item is None:
                break
            results.append(item)
        return results

    def stop(self):
        """Stop the server"""
        self.server_running = False
        if self.server_socket:
            self.server_socket.close()
        if self._server_thread:
            self._server_thread.join(timeout=2.0)
        print("Server stopped")

    def _create_server_socket(self):
        self.port = self._select_free_port(self.port_range, self.host)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.server_socket.settimeout(1.0)  # Allow checking self.running periodically
        self.server_running = True

        self._server_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._server_thread.start()
        self.log.info(f"Socket Server started on {self.host}:{self.port}")


    async def _start_maxima_instance(self, maxima_path: str):
        self.maxima_instance = await asyncio.create_subprocess_shell(f"{maxima_path} -s {self.port}", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)



    def start_instance(self):
        self.log.info(f"Starting Server Socket for Maxima at {self.host}")
        self._create_server_socket()
        self.log.info(f"Maxima initiated, connect to  {self.host}:{self.port}")
        asyncio.run(self._start_maxima_instance(self.maxima_path))
        self.log.info("Confirming connection with Maxima")
        self.maxima_status = "INIT"
        wait_time = 0
        while self.maxima_status != "READY":
            time.sleep(1)
            response = self.get_response(block=True, timeout=1)
            if response is not None:
                self.log.debug(response['response'])

                if is_max_prompt.match(response['response']):
                    self.log.info("Maxima is ready for input")
                    self.maxima_status = "READY"

            else:
                self.log.debug("No response from Maxima")
            wait_time += 1
            if wait_time > 10:
                self.log.error("Maxima did not respond in time, exiting")
                exit(2)






if __name__ == "__main__":
    maxima_instance = MaximaServer()
    maxima_instance.start_instance()
