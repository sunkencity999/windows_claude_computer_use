"""Windows implementation of the bash tool using cmd.exe"""

import asyncio
import os
import subprocess
from typing import Any, Literal, TypedDict

from anthropic.types.beta import BetaToolParam
from asyncio.subprocess import PIPE
from ..tools.base import BaseAnthropicTool, ToolError, ToolResult


class AsyncWindowsShell:
    """Async wrapper for Windows command shell."""
    
    def __init__(self):
        self._process = None
        self._stderr_task = None
        self._stdout_task = None

    async def start(self):
        """Start a Windows command shell process."""
        # We don't need to maintain a persistent shell process
        pass

    async def _run_system_command(self, command: str) -> tuple[int, str, str]:
        """Execute a Windows system command."""
        try:
            # Run the command with subprocess.run
            process = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,  # Required for system commands
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=30,  # System commands might take longer
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            if process.returncode == 0:
                return 0, process.stdout, process.stderr
            else:
                error_msg = process.stderr if process.stderr else process.stdout
                return process.returncode, f"Command failed with error: {error_msg}", process.stderr
                
        except subprocess.TimeoutExpired:
            return 1, "Command timed out after 30 seconds", ""
        except Exception as e:
            return 1, f"Failed to execute system command: {str(e)}", ""

    async def _run_network_command(self, command: str) -> tuple[int, str, str]:
        """Execute a network command directly using synchronous subprocess."""
        try:
            # Use cmd.exe explicitly for network commands
            full_command = f'cmd.exe /c {command}'
            
            # Run the command with subprocess.run
            process = subprocess.run(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10,  # 10 second timeout
                text=True,   # Automatically decode output as text
                encoding='utf-8',  # Try UTF-8 first
                errors='ignore'  # Ignore any decoding errors
            )
            
            if process.returncode == 0:
                return 0, process.stdout, process.stderr
            else:
                error_msg = process.stderr if process.stderr else process.stdout
                return process.returncode, f"Command failed with error: {error_msg}", process.stderr
                
        except subprocess.TimeoutExpired:
            return 1, "Command timed out after 10 seconds", ""
        except Exception as e:
            return 1, f"Failed to execute command: {str(e)}", ""

    async def _run_system_cmd(self, command: str) -> tuple[int, str, str]:
        """Execute a Windows system command."""
        try:
            # Define common system32 paths
            system32_path = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32')
            cmd_path = os.path.join(system32_path, 'cmd.exe')
            
            # Get the command base name
            base_cmd = command.split()[0].lower()
            
            # If it's a system command, try to find its full path
            if base_cmd in ['systeminfo', 'wmic', 'tasklist']:
                cmd_exe = os.path.join(system32_path, f"{base_cmd}.exe")
                if os.path.exists(cmd_exe):
                    # Replace the command with its full path
                    command = f"{cmd_exe} {' '.join(command.split()[1:])}"
            
            # Create the full command with proper environment setup
            full_command = f'"{cmd_path}" /c "{command}"'
            
            # Set up the environment with system32 path
            env = os.environ.copy()
            env['PATH'] = f"{system32_path};{env.get('PATH', '')}"
            
            # Run the command synchronously
            result = subprocess.run(
                full_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW,
                env=env,
                cwd=system32_path  # Run from System32 directory
            )
            
            if result.returncode == 0:
                return 0, result.stdout, result.stderr
            else:
                error = result.stderr if result.stderr else result.stdout
                return result.returncode, f"Command failed: {error}", result.stderr
        except Exception as e:
            error_msg = f"""Failed to execute system command:
Command: {command}
Error: {str(e)}
System32 Path: {system32_path}
Command Exists: {os.path.exists(cmd_path)}"""
            return 1, error_msg, ""

    async def run(self, command: str) -> tuple[int, str, str]:
        """Run a command in the shell and return exit code, stdout, and stderr."""
        # Get base command for routing
        base_cmd = command.split()[0].lower()
        
        # Handle system commands
        system_commands = {
            'systeminfo', 'wmic', 'ver', 'powershell',
            'sc', 'net', 'reg', 'tasklist', 'schtasks',
            'gpresult', 'whoami', 'hostname'
        }
        
        if base_cmd in system_commands:
            return await self._run_system_cmd(command)
            
        # Handle network commands
        if base_cmd in ['ping', 'ipconfig', 'netstat', 'tracert', 'nslookup']:
            return await self._run_network_command(command)
        try:
            cwd = os.getcwd()
            
            # Define system commands that need special handling
            system_commands = {
                'systeminfo', 'wmic', 'ver', 'gpresult',
                'schtasks', 'sc', 'net', 'reg'
            }

            # Special handling for common Windows commands
            # Define command mappings with their Windows equivalents
            simple_commands = {
                # Basic file and directory operations
                'dir': 'dir',
                'cd': 'cd',
                'pwd': 'cd',
                'type': lambda x: f'type "{x}"',
                'copy': lambda x, y: f'copy "{x}" "{y}"',
                'move': lambda x, y: f'move "{x}" "{y}"',
                'del': lambda x: f'del "{x}"',
                'erase': lambda x: f'del "{x}"',  # alias for del
                'ren': lambda x, y: f'ren "{x}" "{y}"',
                'rename': lambda x, y: f'ren "{x}" "{y}"',  # alias for ren
                'echo': lambda x: f'echo {x}',
                
                # Directory management
                'tree': 'tree',  # show directory structure
                'chdir': 'cd',   # alias for cd
                'rd': lambda x: f'rd "{x}"',  # alias for rmdir
                
                # File management
                'comp': lambda x, y: f'comp "{x}" "{y}"',  # compare two files
                'fc': lambda x, y: f'fc "{x}" "{y}"',      # file compare
                'find': lambda x: f'find "{x}"',           # find text in files
                'findstr': lambda x: f'findstr "{x}"',     # find strings in files
                'attrib': lambda x: f'attrib "{x}"',       # display/change file attributes
                
                # System information
                'ver': 'ver',          # display Windows version
                'vol': 'vol',          # display volume label
                'systeminfo': 'systeminfo',  # detailed system information
                'tasklist': 'tasklist',     # list running processes
                'where': lambda x: f'where "{x}"',  # locate programs
                'whoami': 'whoami',     # display current user
                
                # Network commands
                'ipconfig': 'ipconfig',  # display network configuration
                'netstat': 'netstat',    # display network statistics
                'ping': lambda x: f'ping {x}',  # test network connection
                'hostname': 'hostname',  # display computer name
                
                # Time and date
                'time': 'time /t',     # display current time
                'date': 'date /t',     # display current date
                
                # File system
                'chkdsk': lambda x='': f'chkdsk {x}',  # check disk
                'compact': lambda x: f'compact "{x}"',  # compress files
                'fsutil': lambda x: f'fsutil {x}',      # file system utility
                
                # Text processing
                'sort': lambda x: f'sort "{x}"',    # sort text
                'more': lambda x: f'more "{x}"',    # display output one screen at a time
                'clip': lambda x: f'clip < "{x}"',  # copy to clipboard
                
                # Batch file commands
                'call': lambda x: f'call "{x}"',    # call another batch file
                'title': lambda x: f'title {x}',    # set window title
                
                # Environment
                'set': lambda x: f'set {x}',        # display/set environment variables
                'path': 'path',                     # display/set PATH
                
                # Special commands
                'cls': 'cls',          # clear screen
                'exit': 'exit',        # exit command prompt
                'help': lambda x='': f'help {x}',  # get help on commands
                'prompt': lambda x: f'prompt {x}',  # change command prompt
                
                # Power management
                'shutdown': lambda x='/s': f'shutdown {x}',  # shutdown computer
                'powercfg': lambda x: f'powercfg {x}',      # power configuration
                
                # Security and permissions
                'cacls': lambda x: f'cacls "{x}"',    # display/edit file ACLs
                'icacls': lambda x: f'icacls "{x}"',  # improved cacls
                
                # Disk management
                'diskpart': 'diskpart',  # disk partitioning
                'defrag': lambda x: f'defrag "{x}"',  # defragment disk
                
                # Service management
                'sc': lambda x: f'sc {x}',  # service control
                'net': lambda x: f'net {x}'  # network services and resources
            }
            
            # Extract the base command
            base_cmd = command.split()[0].lower()
            
            if base_cmd in simple_commands:
                try:
                    # Get all arguments after the command
                    args = command.split(None, 1)[1] if len(command.split()) > 1 else ''
                    
                    # Handle different command types
                    if callable(simple_commands[base_cmd]):
                        if base_cmd in ['copy', 'move', 'ren', 'rename', 'comp', 'fc']:
                            # Commands that require exactly two arguments
                            try:
                                src, dst = args.rsplit(None, 1)
                                cmd = simple_commands[base_cmd](src.strip('"'), dst.strip('"'))
                            except ValueError:
                                return 1, f"Error: {base_cmd} command requires two arguments (source and destination)", ""
                        
                        elif base_cmd in ['sc', 'net', 'fsutil', 'powercfg']:
                            # Commands that pass through arguments unchanged
                            cmd = simple_commands[base_cmd](args)
                        
                        elif base_cmd == 'ping':
                            # Special handling for ping command
                            # Strip any quotes and ensure only 4 pings by default
                            target = args.strip().strip('"')
                            if not any(switch in args.lower() for switch in ['-n', '/n']):
                                target = f"-n 4 {target}"  # Add default count if not specified
                            cmd = f"ping {target}"
                        
                        elif base_cmd in ['find', 'findstr']:
                            # Search commands need special handling for multiple arguments
                            cmd = simple_commands[base_cmd](args.replace('"', '""'))
                        
                        elif base_cmd in ['help', 'chkdsk']:
                            # Commands that work with or without arguments
                            cmd = simple_commands[base_cmd](args) if args else simple_commands[base_cmd]()
                        
                        else:
                            # Default single argument handling
                            cmd = simple_commands[base_cmd](args.strip('"'))
                    else:
                        # Commands that don't need argument processing
                        cmd = simple_commands[base_cmd]
                        
                    # Add any common switches for better output
                    if base_cmd == 'find':
                        cmd += ' /N'  # Add line numbers
                    elif base_cmd == 'tree':
                        cmd += ' /F'  # Show files in addition to directories
                    elif base_cmd in ['tasklist', 'netstat']:
                        cmd += ' /FO TABLE'  # Format as table
                        
                except Exception as e:
                    return 1, f"Error processing {base_cmd} command: {str(e)}", ""
                
                # Network commands need shell=True to work properly
                use_shell = base_cmd in ['ping', 'ipconfig', 'netstat', 'tracert', 'nslookup']
                
                process = await asyncio.create_subprocess_shell(
                    f'cmd /c {cmd}',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    shell=use_shell
                )
                stdout, stderr = await process.communicate()
                try:
                    output = stdout.decode('utf-8') if stdout else ''
                except UnicodeDecodeError:
                    output = stdout.decode('cp1252', errors='ignore') if stdout else ''
                
                if process.returncode == 0:
                    return 0, output or f"Successfully executed {base_cmd} command", ""
                else:
                    error = stderr.decode('utf-8', errors='ignore') if stderr else "Command failed"
                    return process.returncode, error, ""

            # Special handling for directory creation
            if command.lower().startswith(('md ', 'mkdir ')):
                try:
                    # Extract directory name
                    dir_name = command.split('"')[1] if '"' in command else command.split(' ', 1)[1]
                    # Create directory directly using Python
                    os.makedirs(dir_name, exist_ok=True)
                    return 0, f"Successfully created directory: {dir_name}", ""
                except Exception as dir_e:
                    return 1, f"Failed to create directory: {str(dir_e)}", ""
            
            # Special handling for directory removal
            elif command.lower().startswith(('rmdir ', 'rd ')):
                try:
                    # Parse command
                    parts = command.split()
                    force_remove = '/s' in parts
                    # Get directory name (handling quotes)
                    if '"' in command:
                        dir_name = command.split('"')[1]
                    else:
                        dir_name = next(part for part in parts[1:] if not part.startswith('/'))
                    
                    if force_remove:
                        import shutil
                        shutil.rmtree(dir_name)
                    else:
                        os.rmdir(dir_name)
                    return 0, f"Successfully removed directory: {dir_name}", ""
                except FileNotFoundError:
                    return 1, f"Directory not found: {dir_name}", ""
                except OSError as e:
                    if e.errno == 39 or "directory not empty" in str(e).lower():
                        return 1, f"Directory not empty: {dir_name}. Use 'rmdir /s {dir_name}' to remove directory and its contents.", ""
                    return 1, f"Failed to remove directory: {str(e)}", ""
            
            # For other commands
            # Create a wrapped PowerShell command that captures output
            # Escape any double quotes in the command
            escaped_command = command.replace('"', '`"')
            
            ps_command = (
                '$ErrorActionPreference = "Stop"; '
                '$output = @{}; '
                'try { '
                    f'$process = Start-Process -FilePath "cmd.exe" -ArgumentList "/c {escaped_command}" -NoNewWindow -Wait -PassThru; '
                    '$output.exitcode = $process.ExitCode; '
                    '$output.stdout = "Command executed"; '
                    '$output.stderr = ""; '
                '} '
                'catch { '
                    '$output.exitcode = 1; '
                    '$output.stdout = ""; '
                    '$output.stderr = $_.Exception.Message; '
                '} '
                '$output | ConvertTo-Json;'
            )
            
            # Run the PowerShell command
            process = await asyncio.create_subprocess_shell(
                f'powershell.exe -Command "{ps_command}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                cwd=cwd
            )

            stdout, stderr = await process.communicate()
            
            try:
                stdout_str = stdout.decode('utf-8') if stdout else ''
                stderr_str = stderr.decode('utf-8') if stderr else ''
            except UnicodeDecodeError:
                stdout_str = stdout.decode('cp1252') if stdout else ''
                stderr_str = stderr.decode('cp1252') if stderr else ''

            # Check if the command seems to have succeeded
            if process.returncode == 0:
                # Verify the directory was created by checking dir output again
                verify_process = await asyncio.create_subprocess_shell(
                    'dir',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                verify_out, _ = await verify_process.communicate()
                verify_str = verify_out.decode('utf-8', errors='ignore')
                
                if command.lower().startswith(('md ', 'mkdir ')):
                    # Extract directory name and check if it appears in the new listing
                    dir_name = command.split('"')[1] if '"' in command else command.split(' ', 1)[1]
                    if dir_name.lower() not in verify_str.lower():
                        return 1, f"Directory creation failed. Current directory contents:\n{verify_str}", ""
                
                return 0, "Command executed successfully", ""
            else:
                error_output = stderr_str if stderr_str else stdout_str
                diagnostic = f"Command failed: {error_output if error_output else 'Unknown error'}"
                return process.returncode, diagnostic, stderr_str

        except Exception as e:
            # For directory commands, try direct execution
            if command.lower() in ['dir', 'cd']:
                try:
                    dir_out = subprocess.check_output('dir', shell=True).decode('utf-8', errors='ignore')
                    return 0, dir_out, ''
                except Exception as dir_e:
                    return 1, f"Failed to get directory listing: {str(dir_e)}", ''
            
            # For other commands, just show the error
            error_msg = f"Command failed: {str(e)}"
            return 1, error_msg, ''

    async def stop(self):
        """Stop the shell process."""
        if self._process is not None:
            try:
                self._process.terminate()
                await self._process.wait()
            except ProcessLookupError:
                pass
            self._process = None


class BashTool(BaseAnthropicTool):
    """
    A tool that allows the agent to run commands in a Windows command shell.
    The tool parameters are defined by Anthropic and are not editable.
    """

    name: Literal["bash"] = "bash"
    api_type: Literal["bash_20241022"] = "bash_20241022"
    _session: AsyncWindowsShell

    def __init__(self):
        super().__init__()
        self._session = AsyncWindowsShell()
    
    def to_params(self) -> BetaToolParam:
        """Convert this tool to its API parameters."""
        return {"name": self.name, "type": self.api_type}

    async def __call__(
        self,
        *,
        command: str | None = None,
        restart: bool | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Run a command in the Windows command shell."""
        if restart:
            await self._session.stop()
            return ToolResult()

        if not command:
            raise ToolError("command is required")

        returncode, stdout, stderr = await self._session.run(command)
        
        if returncode != 0:
            if stderr:
                return ToolResult(error=stderr)
            else:
                return ToolResult(error=stdout if stdout else "Command failed")

        return ToolResult(output=stdout.strip() if stdout else "Command executed successfully")