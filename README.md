# Telegram Assistant

This is a modular Python application that allows you to run commands on your remote server, in my case a Raspberry Pi (Linux Raspbian), using Telegram. You will create your own Telegram Bot (assistant) and be able to run commands and scripts on/from your server via this modular architecture.

> The main Python file is still called `telegrambot.py` for backward compatibility.

---

### What is this repository for?

* Telegram Assistant (personal Telegram bot for remote control)
* Version 5.0

---

#### What's new in version 5.0?

* **Complete architectural overhaul**: The bot now uses a modular plugin-based architecture for easy extensibility
* **Dynamic command loading**: Commands are automatically loaded from the `commands/` directory
* **Separation of concerns**: Core functionality is separated into logical modules in the `core/` directory
* **Easy extensibility**: Add new command categories by simply dropping Python files into the `commands/` folder
* **Better error handling**: Improved error handling and logging throughout the application
* **Type hints**: Full type hint support for better code documentation and IDE support
* **Abstract base classes**: Consistent interfaces for all command handlers
* **Individual testing**: Each command handler can be tested independently
* **Timeout protection**: All shell commands now have timeout protection for safety


#### What has been added in version 4.2?

* **New URL fetch feature**. Send `url <https://...>` or just paste an `http[s]://` link and the bot will fetch the page and reply with cleaned plain text (scripts/styles stripped). Long pages are split into multiple Telegram messages.
* The helper script `fetch_clean_url.py` is now located in the `utils` folder.
* Updated environment and requirements guidance. `requests` and `beautifulsoup4` are now core. `lxml` and `readability-lxml` are optional but recommended for better parsing. Raspberry Pi build tips included.
* Minor tidy ups in README wording.

#### What has been added in version 4.1?

* Minor improvements and stability fixes.

#### What has been added in version 4.0?

* Python isolation installation instructions (virtual environment) to follow best practises.
* Reworked the script to use the most recent and supported Python library `python-telegram-bot`.
* Updated the startup oneliner to reflect the changes of running the script in isolation.

#### What has been added in version 3.0?

* New `exec` function that allows you to pass a full shell command via the Telegram bot. This is a very DANGEROUS risk that can DESTROY your server and setup completely. However, in case of emergencies, it can save you. Use it wisely. And yes, they will run as `root`.
* Random generated password, required to run any command issued via `exec` function. This is a way to be sure you are the one running the command.
* 3 attempts before the password expires.
* Password sent via email (this needs to be configured in the `config.py` script).

NOTE: the `exec` function works ONLY if you set the script to send you the password via email. The script requires SMTP, username and password to send the email, and of course, the recipient who is going to receive the email. Without the password, no `exec` commands can be executed.

---

### Project Structure

```
telegram-assistant/
├── telegrambot.py              # Main application (backward compatibility name)
├── config.py                   # Configuration file (copy from config.py.template)
├── config.py.template          # Configuration template
├── requirements.txt            # Python dependencies
├── core/                       # Core functionality modules
│   ├── __init__.py
│   ├── auth.py                # Authentication management
│   ├── command_loader.py      # Dynamic command loading system
│   ├── message_utils.py       # Message handling utilities
│   └── shell_utils.py         # Shell command execution utilities
├── commands/                  # Command handler plugins
│   ├── __init__.py
│   ├── system_commands.py     # Basic system commands (uptime, df, last)
│   ├── service_commands.py    # Service management (vpn-restart, kodi, etc.)
│   ├── restart_commands.py    # Device restart commands
│   ├── url_fetch.py           # URL fetching functionality (print website content)
│   ├── exec_commands.py       # Secure command execution with email verification
│   └── windows_commands.py    # Windows machine management
└── utils/                     # Utility scripts and samples
│   └── fetch_clean_url.py     # URL content fetching 
└── extras/                    # Collection of extra tools and scripts 
    └── [other utility scripts]
```

---

### Available Commands

The modular architecture supports the following command categories:

**System Commands**: `uptime`, `df`, `last`
**Service Management**: `vpn-restart`, `kodi stop`, `kodi start`, `upgrade raspbxino`, `tunnel-ssh`
**Device Restarts**: `restart router`, `restart raspberrino`, `restart raspbxino`
**URL Fetching**: `url <https://...>`, `fetch <https://...>`, or just paste an `http[s]://` link
**Secure Execution**: `exec <custom shell command>` (requires email verification)
**Windows Management**: `shutdown-nuky`

The bot automatically displays available commands when you send an unrecognized command.

---

### How do I get set up?

* Clone the repository.

* Make sure Python 3.11+ is installed (earlier 3.9+ usually fine but 3.11 recommended).

* Create a Python virtual environment (recommended for isolation):

  ```bash
  python3 -m venv telegram_bot
  source telegram_bot/bin/activate
  ```

* Install Python dependencies using `requirements.txt`:

  ```bash
  pip install -r requirements.txt
  ```

  > **Note about optional parsing extras**
  > The URL fetch feature works with just `requests` and `beautifulsoup4`. Installing `lxml` and `readability-lxml` improves parsing quality but can be heavy to build on Raspberry Pi.

* If you plan to install `lxml` (recommended but optional), install the system build packages first (Raspberry Pi / Debian):

  ```bash
  sudo apt update
  sudo apt install -y python3-dev build-essential libxml2-dev libxslt1-dev zlib1g-dev
  ```

  Then uncomment the optional dependencies in `requirements.txt` and reinstall:

  ```bash
  pip install --upgrade -r requirements.txt
  ```

  If build time is long or fails, keep `lxml` and `readability-lxml` commented out in `requirements.txt` and the bot will fall back to the built-in HTML parser.

* Copy `config.py.template` to `config.py` and follow the instructions to fill up the variables.

* Test running `python telegrambot.py` from inside the virtual environment.

> NOTE: This script uses the `python-telegram-bot` library with asynchronous functions. On environments like Raspberry Pi OS you may encounter issues with `asyncio` because of an already running event loop. This is automatically handled using `nest_asyncio`.

---

### Adding New Commands

The modular architecture makes it easy to add new command categories:

1. Create a new Python file in the `commands/` directory
2. Import the base class: `from core.command_loader import BaseCommandHandler`
3. Create your handler class inheriting from `BaseCommandHandler`
4. Implement the required methods: `can_handle()`, `execute()`, and `get_help()`
5. The bot will automatically load your new commands on startup

Example minimal command handler:

```python
from core.command_loader import BaseCommandHandler
from core.shell_utils import ShellExecutor

class MyCommandHandler(BaseCommandHandler):
    async def can_handle(self, command: str) -> bool:
        return command == 'mycommand'
    
    async def execute(self, message, command: str):
        result = ShellExecutor.execute_command(['echo', 'Hello World'])
        await message.reply_text(result)
    
    async def get_help(self) -> str:
        return "My Commands: mycommand"
```

---

### Testing Individual Handlers

You can test individual command handlers independently:

```python
import asyncio
from commands.system_commands import SystemCommandHandler

async def test_handler():
    handler = SystemCommandHandler()
    can_handle = await handler.can_handle('uptime')
    help_text = await handler.get_help()
    print(f"Can handle 'uptime': {can_handle}")
    print(f"Help: {help_text}")

asyncio.run(test_handler())
```

---

### Sudoers Configuration

All bot commands that need root privileges must be properly set in the `sudoers` file.

Example sudoers configuration:

```
myuser ALL=(ALL) NOPASSWD:/sbin/reboot
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/restart_device
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/manage_kodi
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/upgrade_raspbxino
myuser ALL=(ALL) NOPASSWD:/bin/systemctl restart openvpn.service
myuser ALL=(ALL) NOPASSWD:/tmp/temp-telegram-script.sh
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/shutdown-nuky
```

I have custom scripts in `/usr/local/bin` and those scripts require root privileges. I can call those scripts via my bot, but the user `myuser` (the one who is running this Telegram bot script) has to be properly configured to grant those privileges when running the script.

**Do not forget this step** ;-)

---

### Security Features

#### Exec Command Security

The `exec` command allows running arbitrary shell commands but includes multiple security layers:

* **Email verification**: A random password is generated and sent to your configured email
* **Limited attempts**: Only 3 password attempts before expiration
* **Temporary files**: All temporary files are cleaned up after execution
* **Audit trail**: All exec commands are logged with timestamps

To use the exec function, you must configure SMTP settings in `config.py`:
- `email_address`: Your SMTP email address
- `email_password`: Your SMTP password
- `recipient_email`: Email address to receive passwords
- `smtp_server`: SMTP server address
- `smtp_port`: SMTP server port

#### General Security

* **User authentication**: Only authorized user IDs and usernames can access the bot
* **Bot protection**: Prevents other bots from using your bot
* **Timeout protection**: All shell commands have 30-second timeouts
* **Error isolation**: Errors in one command handler don't affect others

---

### Scripts in utils folder

The folder `utils` contains utility scripts that support the main application:

* **fetch_clean_url.py**: Helper script for the URL fetching functionality. Extracts clean text from web pages.

---

### Files in extras folder

Additional utility scripts for autostart and monitoring.  
These files are not used by the main project and are here just as samples.  

---

### Architecture Benefits

1. **Easy to extend**: Just drop a new Python file in the `commands/` directory
2. **Single responsibility**: Each handler manages one type of command
3. **Testable**: Each handler can be unit tested independently
4. **Maintainable**: Changes to one command type don't affect others
5. **Clear structure**: Easy to understand and navigate
6. **Automatic loading**: New commands are discovered automatically
7. **Type safety**: Full type hints for better development experience
8. **Error isolation**: Problems in one handler don't crash the entire bot

---

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).



































# Telegram Assistant

This is a Python script that allows you to run commands on your remote server, in my case a Raspberry Pi (Linux Raspbian), using Telegram.
In fact, you will create your own Telegram Bot (assistant) and you will be able to run commands and scripts on/from your server via this script.

> The project was previously referred to informally as "Telegram Bot". The main Python file is still called `telegrambot.py` for backward compatibility.

---

### What is this repository for?

* Telegram Assistant (personal Telegram bot for remote control)
* Version 4.2

---

#### What has been added in version 4.2?

* **New URL fetch feature**. Send `url <https://...>` or just paste an `http[s]://` link and the bot will fetch the page and reply with cleaned plain text (scripts/styles stripped). Long pages are split into multiple Telegram messages.
* The helper script `fetch_clean_url.py` is now located in the `utils` folder.
* Updated environment and requirements guidance. `requests` and `beautifulsoup4` are now core. `lxml` and `readability-lxml` are optional but recommended for better parsing. Raspberry Pi build tips included.
* Minor tidy ups in README wording.

#### What has been added in version 4.1?

* Minor improvements and stability fixes.

#### What has been added in version 4.0?

* Python isolation installation instructions (virtual environment) to follow best practises.
* Reworked the script to use the most recent and supported Python library `python-telegram-bot`.
* Updated the startup oneliner to reflect the changes of running the script in isolation.

#### What has been added in version 3.0?

* New `exec` function that allows you to pass a full shell command via the Telegram bot. This is a very DANGEROUS risk that can DESTROY your server and setup completely. However, in case of emergencies, it can save you. Use it wisely. And yes, they will run as `root`.
* Random generated password, required to run any command issued via `exec` function. This is a way to be sure you are the one running the command.
* 3 attempts before the password expires.
* Password sent via email (this needs to be configured in the `config.py` script).

NOTE: the `exec` function works ONLY if you set the script to send you the password via email. The script requires SMTP, username and password to send the email, and of course, the recipient who is going to receive the email. Without the password, no `exec` commands can be executed.

---

### How do I get set up?

* Clone the repository.

* Make sure Python 3.11+ is installed (earlier 3.9+ usually fine but 3.11 recommended).

* Make sure the Debian/Linux package `logger` is installed too if you use the custom startup script that logs automatically.

* Create a Python virtual environment (recommended for isolation):

  ```bash
  python3 -m venv telegram_bot
  source telegram_bot/bin/activate
  ```

* Install Python dependencies using `requirements.txt`:

  ```bash
  pip install -r requirements.txt
  ```

  > **Note about optional parsing extras**
  > The URL fetch feature works with just `requests` and `beautifulsoup4`. Installing `lxml` and `readability-lxml` improves parsing quality but can be heavy to build on Raspberry Pi. See below.

* If you plan to install `lxml` (recommended but optional), install the system build packages first (Raspberry Pi / Debian):

  ```bash
  sudo apt update
  sudo apt install -y python3-dev build-essential libxml2-dev libxslt1-dev zlib1g-dev
  ```

  Then reinstall the Python deps:

  ```bash
  pip install --upgrade -r requirements.txt
  ```

  If build time is long or fails, comment out `lxml` and `readability-lxml` in `requirements.txt` and the bot will fall back to the built in HTML parser.

* Copy `config.py.template` to `config.py` and follow the instructions to fill up the variables.

* Edit `telegrambot.py` accordingly. This is the main file where you can set all your actions. Mine is an example.

* Do not move the `fetch_clean_url.py` script out of the `utils/` folder: the bot calls it by relative path `utils/fetch_clean_url.py` from its own directory. Just make sure it is executable:

  ```bash
  chmod +x utils/fetch_clean_url.py
  ```

* Test running `python telegrambot.py` from inside the virtual environment.

> NOTE: This script uses the `python-telegram-bot` library with asynchronous functions. On environments like Raspberry Pi OS you may encounter issues with `asyncio` because of an already running event loop. This is automatically handled using `nest_asyncio`.

---

### Notes

My `telegrambot.py` script is a combination of OS commands and custom scripts called by this bot. You can use the same combination. What is easy to do with few *words* is probably worth leaving as it is, but when you need to do something more complex (for example ssh into another server and run a command) just create your own script and call it within this bot.

Do not forget that ALL THE BOT COMMANDS that need root privileges must be properly set in the `sudoers` file.

Example:

```
myuser ALL=(ALL) NOPASSWD:/sbin/reboot
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/restart_device
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/manage_kodi
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/upgrade_raspbxino
myuser ALL=(ALL) NOPASSWD:/bin/systemctl restart openvpn.service
myuser ALL=(ALL) NOPASSWD:/tmp/temp-telegram-script.sh
```

I have custom scripts in `/usr/local/bin` and those scripts require root privileges. I can call those scripts via my bot, but the user `myuser` (the one who is running this Telegram bot script) has to be properly configured to grant those privileges when running the script.

**Do not forget this step** ;-)

---

### Scripts in utils folder

In the folder `utils` you can find some scripts that may help automate functions like autostart at boot and monitoring checks.

The scripts require changes/updates before being fully functional. Make sure to EDIT/UPDATE them before installing them.

Here is the list of the files:

* **telegrambot\_start.example**: start your bot using the suggested Python custom environment. Ideally copy to `/usr/local/bin/telegrambot_start`. Remember `chmod +x` and update paths and username.
* **check\_telegrambot\_connection.monit-check**: use with Monit to verify the bot is running. Ideally copy to `/usr/local/bin/check_telegrambot_connection` and `chmod +x`.
* **telegrambot.monit-config**: sample Monit config file. Copy to `/etc/monit/conf-available/telegram_bot` (update the user) and enable per Monit instructions.
* **rc.local.append**: append to your `rc.local` to auto start the script at boot. Update with the actual user before appending.
* **check\_telegrambot.nagios**: old script for Nagios. No longer maintained but kept as an example.
* **fetch\_clean\_url.py**: helper script to fetch and clean webpage text for the `url` command.

---

### Helper script for fetching clean web page text

This could be handy if you're on the plane, with free messages only, but you have a few articles that you wanted to finish to read.  
The bot supports fetching and cleaning webpage content via a helper script located at `utils/fetch_clean_url.py`.
* The script fetches the given URL and extracts the main readable text, stripping away ads, navigation, and other clutter.
* The Telegram bot calls this script internally using a relative path, so do not move the script out of the `utils/` folder.
* Make sure the script is executable:
  ```bash
   chmod +x utils/fetch_clean_url.py
  ```
* You can test the script manually by running:
  ```bash
  python utils/fetch_clean_url.py <URL>
  ```
* The script outputs clean UTF-8 text, and the bot automatically splits long results into multiple Telegram messages to avoid Telegram's message size limits.


--

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

