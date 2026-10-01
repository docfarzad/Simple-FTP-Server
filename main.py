import os
import socket
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


# ============================================================
# FTP SERVER
# ============================================================

class FTPServer:
    def __init__(self, root, username, password, port):
        self.root = Path(root).resolve()
        self.username = username
        self.password = password
        self.port = int(port)

        self.sock = None
        self.running = False
        self.thread = None

    # --------------------------------------------------------
    # Find local IPv4 address
    # --------------------------------------------------------

    @staticmethod
    def get_local_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            # No data actually needs to be sent.
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"
        finally:
            s.close()

    # --------------------------------------------------------
    # Start
    # --------------------------------------------------------

    def start(self):
        self.root.mkdir(parents=True, exist_ok=True)

        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        self.sock.bind(("0.0.0.0", self.port))
        self.sock.listen(20)

        self.running = True

        self.thread = threading.Thread(
            target=self.accept_clients,
            daemon=True
        )

        self.thread.start()

    # --------------------------------------------------------
    # Stop
    # --------------------------------------------------------

    def stop(self):
        self.running = False

        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

            self.sock = None

    # --------------------------------------------------------
    # Accept clients
    # --------------------------------------------------------

    def accept_clients(self):
        while self.running:
            try:
                client, address = self.sock.accept()

                threading.Thread(
                    target=self.client_thread,
                    args=(client,),
                    daemon=True
                ).start()

            except OSError:
                break

    # --------------------------------------------------------
    # Send FTP response
    # --------------------------------------------------------

    @staticmethod
    def send(conn, text):
        conn.sendall(
            (text + "\r\n").encode("utf-8")
        )

    # --------------------------------------------------------
    # Keep paths inside shared folder
    # --------------------------------------------------------

    def safe_path(self, cwd, path):
        if not path:
            return cwd

        if path.startswith("/"):
            candidate = (
                self.root / path.lstrip("/")
            ).resolve()
        else:
            candidate = (
                cwd / path
            ).resolve()

        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise PermissionError(
                "Path outside shared folder"
            )

        return candidate

    # --------------------------------------------------------
    # FTP client
    # --------------------------------------------------------

    def client_thread(self, conn):
        cwd = self.root

        logged_in = False
        username = None

        data_listener = None
        rename_source = None

        try:
            self.send(
                conn,
                "220 Simple Python FTP Server"
            )

            buffer = b""

            while True:

                # Read until CRLF
                while b"\r\n" not in buffer:
                    data = conn.recv(4096)

                    if not data:
                        return

                    buffer += data

                line, buffer = buffer.split(
                    b"\r\n",
                    1
                )

                command = line.decode(
                    "utf-8",
                    errors="replace"
                )

                parts = command.split(" ", 1)

                cmd = parts[0].upper()
                arg = parts[1] if len(parts) > 1 else ""

                # ==================================================
                # LOGIN
                # ==================================================

                if cmd == "USER":
                    username = arg
                    self.send(
                        conn,
                        "331 Password required"
                    )
                    continue

                if cmd == "PASS":
                    if (
                        username == self.username
                        and arg == self.password
                    ):
                        logged_in = True

                        self.send(
                            conn,
                            "230 Login successful"
                        )
                    else:
                        self.send(
                            conn,
                            "530 Login incorrect"
                        )

                    continue

                if not logged_in:
                    self.send(
                        conn,
                        "530 Please login first"
                    )
                    continue

                # ==================================================
                # BASIC FTP
                # ==================================================

                if cmd == "SYST":
                    self.send(
                        conn,
                        "215 UNIX Type: Python"
                    )

                elif cmd == "TYPE":
                    self.send(
                        conn,
                        "200 Type set"
                    )

                elif cmd == "NOOP":
                    self.send(
                        conn,
                        "200 OK"
                    )

                elif cmd == "FEAT":
                    self.send(
                        conn,
                        "211 End"
                    )

                elif cmd == "QUIT":
                    self.send(
                        conn,
                        "221 Goodbye"
                    )
                    break

                # ==================================================
                # CURRENT DIRECTORY
                # ==================================================

                elif cmd == "PWD":

                    relative = cwd.relative_to(
                        self.root
                    )

                    if str(relative) == ".":
                        ftp_path = "/"
                    else:
                        ftp_path = "/" + str(
                            relative
                        ).replace(os.sep, "/")

                    self.send(
                        conn,
                        f'257 "{ftp_path}"'
                    )

                elif cmd == "CWD":

                    try:
                        new_path = self.safe_path(
                            cwd,
                            arg
                        )

                        if new_path.is_dir():
                            cwd = new_path

                            self.send(
                                conn,
                                "250 Directory changed"
                            )
                        else:
                            self.send(
                                conn,
                                "550 Not a directory"
                            )

                    except Exception:
                        self.send(
                            conn,
                            "550 Invalid path"
                        )

                elif cmd == "CDUP":

                    if cwd != self.root:
                        cwd = cwd.parent

                    self.send(
                        conn,
                        "250 Directory changed"
                    )

                # ==================================================
                # PASSIVE MODE
                # ==================================================

                elif cmd == "PASV":

                    if data_listener:
                        try:
                            data_listener.close()
                        except OSError:
                            pass

                    data_listener = socket.socket(
                        socket.AF_INET,
                        socket.SOCK_STREAM
                    )

                    data_listener.setsockopt(
                        socket.SOL_SOCKET,
                        socket.SO_REUSEADDR,
                        1
                    )

                    data_listener.bind(
                        ("0.0.0.0", 0)
                    )

                    data_listener.listen(1)

                    port = (
                        data_listener
                        .getsockname()[1]
                    )

                    # Actual local IPv4
                    local_ip = self.get_local_ip()

                    p1 = port // 256
                    p2 = port % 256

                    ip_parts = local_ip.split(".")

                    self.send(
                        conn,
                        "227 Entering Passive Mode "
                        f"({','.join(ip_parts)},"
                        f"{p1},{p2})"
                    )

                # ==================================================
                # LIST
                # ==================================================

                elif cmd in ("LIST", "NLST"):

                    if not data_listener:
                        self.send(
                            conn,
                            "425 Use PASV first"
                        )
                        continue

                    try:
                        target = (
                            self.safe_path(cwd, arg)
                            if arg
                            else cwd
                        )

                        client, _ = (
                            data_listener.accept()
                        )

                        data_listener.close()
                        data_listener = None

                        self.send(
                            conn,
                            "150 Opening data connection"
                        )

                        if target.is_dir():
                            entries = list(
                                target.iterdir()
                            )
                        else:
                            entries = [target]

                        output = []

                        for item in entries:

                            if cmd == "NLST":
                                output.append(
                                    item.name
                                )
                            else:
                                try:
                                    size = (
                                        item.stat()
                                        .st_size
                                    )
                                except OSError:
                                    size = 0

                                kind = (
                                    "d"
                                    if item.is_dir()
                                    else "-"
                                )

                                output.append(
                                    f"{kind}rw-rw-rw- "
                                    f"1 user user "
                                    f"{size:>12} "
                                    f"{item.name}"
                                )

                        if output:
                            client.sendall(
                                (
                                    "\r\n".join(output)
                                    + "\r\n"
                                ).encode(
                                    "utf-8",
                                    errors="replace"
                                )
                            )

                        client.close()

                        self.send(
                            conn,
                            "226 Transfer complete"
                        )

                    except Exception:
                        self.send(
                            conn,
                            "550 LIST failed"
                        )

                # ==================================================
                # DOWNLOAD
                # ==================================================

                elif cmd == "RETR":

                    if not data_listener:
                        self.send(
                            conn,
                            "425 Use PASV first"
                        )
                        continue

                    try:
                        file_path = self.safe_path(
                            cwd,
                            arg
                        )

                        if not file_path.is_file():
                            raise FileNotFoundError()

                        client, _ = (
                            data_listener.accept()
                        )

                        data_listener.close()
                        data_listener = None

                        self.send(
                            conn,
                            "150 Opening data connection"
                        )

                        with open(
                            file_path,
                            "rb"
                        ) as f:

                            while True:
                                chunk = f.read(
                                    65536
                                )

                                if not chunk:
                                    break

                                client.sendall(chunk)

                        client.close()

                        self.send(
                            conn,
                            "226 Transfer complete"
                        )

                    except Exception:
                        self.send(
                            conn,
                            "550 Download failed"
                        )

                # ==================================================
                # UPLOAD
                # ==================================================

                elif cmd == "STOR":

                    if not data_listener:
                        self.send(
                            conn,
                            "425 Use PASV first"
                        )
                        continue

                    try:
                        file_path = self.safe_path(
                            cwd,
                            arg
                        )

                        client, _ = (
                            data_listener.accept()
                        )

                        data_listener.close()
                        data_listener = None

                        self.send(
                            conn,
                            "150 Opening data connection"
                        )

                        with open(
                            file_path,
                            "wb"
                        ) as f:

                            while True:
                                chunk = client.recv(
                                    65536
                                )

                                if not chunk:
                                    break

                                f.write(chunk)

                        client.close()

                        self.send(
                            conn,
                            "226 Transfer complete"
                        )

                    except Exception:
                        self.send(
                            conn,
                            "550 Upload failed"
                        )

                # ==================================================
                # DELETE
                # ==================================================

                elif cmd == "DELE":

                    try:
                        path = self.safe_path(
                            cwd,
                            arg
                        )

                        if path.is_file():
                            path.unlink()

                            self.send(
                                conn,
                                "250 File deleted"
                            )
                        else:
                            self.send(
                                conn,
                                "550 Not a file"
                            )

                    except Exception:
                        self.send(
                            conn,
                            "550 Delete failed"
                        )

                # ==================================================
                # MAKE DIRECTORY
                # ==================================================

                elif cmd == "MKD":

                    try:
                        path = self.safe_path(
                            cwd,
                            arg
                        )

                        path.mkdir()

                        self.send(
                            conn,
                            f'257 "{arg}" created'
                        )

                    except Exception:
                        self.send(
                            conn,
                            "550 Directory creation failed"
                        )

                # ==================================================
                # REMOVE DIRECTORY
                # ==================================================

                elif cmd == "RMD":

                    try:
                        path = self.safe_path(
                            cwd,
                            arg
                        )

                        path.rmdir()

                        self.send(
                            conn,
                            "250 Directory removed"
                        )

                    except Exception:
                        self.send(
                            conn,
                            "550 Directory removal failed"
                        )

                # ==================================================
                # RENAME
                # ==================================================

                elif cmd == "RNFR":

                    try:
                        rename_source = self.safe_path(
                            cwd,
                            arg
                        )

                        if rename_source.exists():
                            self.send(
                                conn,
                                "350 Ready for destination"
                            )
                        else:
                            rename_source = None

                            self.send(
                                conn,
                                "550 File not found"
                            )

                    except Exception:
                        rename_source = None

                        self.send(
                            conn,
                            "550 Invalid path"
                        )

                elif cmd == "RNTO":

                    try:
                        if rename_source is None:
                            self.send(
                                conn,
                                "503 Bad sequence"
                            )
                            continue

                        destination = self.safe_path(
                            cwd,
                            arg
                        )

                        rename_source.rename(
                            destination
                        )

                        rename_source = None

                        self.send(
                            conn,
                            "250 Rename successful"
                        )

                    except Exception:
                        self.send(
                            conn,
                            "550 Rename failed"
                        )

                # ==================================================
                # UNKNOWN
                # ==================================================

                else:
                    self.send(
                        conn,
                        "502 Command not implemented"
                    )

        except Exception:
            pass

        finally:

            try:
                if data_listener:
                    data_listener.close()
            except Exception:
                pass

            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# TKINTER APPLICATION
# ============================================================

class App:

    def __init__(self, root):
        self.root = root

        self.root.title(
            "Simple Python FTP Server"
        )

        self.root.geometry(
            "560x400"
        )

        self.root.resizable(
            False,
            False
        )

        self.server = None

        frame = ttk.Frame(
            root,
            padding=20
        )

        frame.pack(
            fill="both",
            expand=True
        )

        # ----------------------------------------------------
        # Folder
        # ----------------------------------------------------

        ttk.Label(
            frame,
            text="Shared folder:"
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=7
        )

        self.folder = tk.StringVar()

        ttk.Entry(
            frame,
            textvariable=self.folder
        ).grid(
            row=0,
            column=1,
            sticky="ew",
            pady=7
        )

        ttk.Button(
            frame,
            text="Browse...",
            command=self.choose_folder
        ).grid(
            row=0,
            column=2,
            padx=(8, 0)
        )

        # ----------------------------------------------------
        # Username
        # ----------------------------------------------------

        ttk.Label(
            frame,
            text="Username:"
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=7
        )

        self.username = tk.StringVar(
            value="user"
        )

        ttk.Entry(
            frame,
            textvariable=self.username
        ).grid(
            row=1,
            column=1,
            columnspan=2,
            sticky="ew"
        )

        # ----------------------------------------------------
        # Password
        # ----------------------------------------------------

        ttk.Label(
            frame,
            text="Password:"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=7
        )

        self.password = tk.StringVar(
            value="password"
        )

        ttk.Entry(
            frame,
            textvariable=self.password,
            show=""
        ).grid(
            row=2,
            column=1,
            columnspan=2,
            sticky="ew"
        )

        # ----------------------------------------------------
        # Port
        # ----------------------------------------------------

        ttk.Label(
            frame,
            text="Port:"
        ).grid(
            row=3,
            column=0,
            sticky="w",
            pady=7
        )

        self.port = tk.StringVar(
            value="2121"
        )

        ttk.Entry(
            frame,
            textvariable=self.port
        ).grid(
            row=3,
            column=1,
            columnspan=2,
            sticky="ew"
        )

        # ----------------------------------------------------
        # Connection information
        # ----------------------------------------------------

        self.address_label = ttk.Label(
            frame,
            text="Server stopped",
            font=("TkDefaultFont", 11)
        )

        self.address_label.grid(
            row=5,
            column=0,
            columnspan=3,
            pady=(20, 5)
        )

        self.login_label = ttk.Label(
            frame,
            text="",
            font=("TkDefaultFont", 10)
        )

        self.login_label.grid(
            row=6,
            column=0,
            columnspan=3,
            pady=3
        )

        # ----------------------------------------------------
        # Start
        # ----------------------------------------------------

        self.start_button = ttk.Button(
            frame,
            text="Start FTP Server",
            command=self.start
        )

        self.start_button.grid(
            row=8,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(20, 5)
        )

        # ----------------------------------------------------
        # Stop
        # ----------------------------------------------------

        self.stop_button = ttk.Button(
            frame,
            text="Stop FTP Server",
            command=self.stop,
            state="disabled"
        )

        self.stop_button.grid(
            row=9,
            column=0,
            columnspan=3,
            sticky="ew"
        )

        frame.columnconfigure(
            1,
            weight=1
        )

    # --------------------------------------------------------
    # Choose folder
    # --------------------------------------------------------

    def choose_folder(self):

        folder = filedialog.askdirectory()

        if folder:
            self.folder.set(folder)

    # --------------------------------------------------------
    # Start server
    # --------------------------------------------------------

    def start(self):

        folder = self.folder.get().strip()
        username = self.username.get()
        password = self.password.get()

        if not folder:
            messagebox.showerror(
                "Error",
                "Choose a folder first."
            )
            return

        if not os.path.isdir(folder):
            messagebox.showerror(
                "Error",
                "The selected folder does not exist."
            )
            return

        if not username:
            messagebox.showerror(
                "Error",
                "Enter a username."
            )
            return

        if not password:
            messagebox.showerror(
                "Error",
                "Enter a password."
            )
            return

        try:
            port = int(self.port.get())

            if not 1 <= port <= 65535:
                raise ValueError

        except ValueError:
            messagebox.showerror(
                "Error",
                "Enter a valid port."
            )
            return

        try:

            self.server = FTPServer(
                folder,
                username,
                password,
                port
            )

            self.server.start()

        except Exception as e:

            self.server = None

            messagebox.showerror(
                "Could not start server",
                str(e)
            )

            return

        local_ip = (
            self.server.get_local_ip()
        )

        self.address_label.config(
            text=f"FTP address: ftp://{local_ip}:{port}"
        )

        self.login_label.config(
            text=(
                f"Username: {username}    "
                f"Password: {password}"
            )
        )

        self.start_button.config(
            state="disabled"
        )

        self.stop_button.config(
            state="normal"
        )

    # --------------------------------------------------------
    # Stop server
    # --------------------------------------------------------

    def stop(self):

        if self.server:
            self.server.stop()
            self.server = None

        self.address_label.config(
            text="Server stopped"
        )

        self.login_label.config(
            text=""
        )

        self.start_button.config(
            state="normal"
        )

        self.stop_button.config(
            state="disabled"
        )

    # --------------------------------------------------------
    # Close application
    # --------------------------------------------------------

    def close(self):

        self.stop()

        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = App(root)

    root.protocol(
        "WM_DELETE_WINDOW",
        app.close
    )

    root.mainloop()