# Simple FTP Server

A lightweight FTP server with a simple desktop interface.

Choose a folder, set a username and password, and start an FTP server that makes the folder available to other devices on your local network.

## Features

* Simple graphical interface built with Tkinter
* Choose any local folder to share
* Username and password authentication
* Read and write access
* Upload and download files
* Create and remove directories
* Delete and rename files
* Displays the local IPv4 address and FTP port
* Pure Python FTP server implementation
* No external FTP server software required
* Can be packaged as a single executable with PyInstaller

## Requirements

* Python 3
* Tkinter
* PyInstaller for building the executable

Install PyInstaller with:

```bash
pip install pyinstaller
```

Tkinter is normally included with standard Python installations. On some Linux distributions, it may need to be installed separately.

## Running from Source

Run:

```bash
python3 main.py
```

The application will open a graphical interface where you can:

1. Select the folder to share.
2. Set the username.
3. Set the password.
4. Choose the FTP port.
5. Start the server.

The application displays an address such as:

```text
ftp://192.168.1.42:2121
```

Use this address from an FTP client on the same network.

## Building a Standalone Executable

Install PyInstaller:

```bash
pip install pyinstaller
```

Build the application as a single executable without a console window:

```bash
PyInstaller --onefile --windowed --name SimpleFTPServer main.py
```

The resulting executable will be placed in:

```text
dist/SimpleFTPServer
```

## Security

This application is intended primarily for trusted local networks.

FTP does **not** encrypt usernames, passwords, or transferred files. Do not expose the server directly to the public internet.

Use a strong password and stop the server when it is no longer needed.


