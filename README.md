# README #

This is a Python script that allows you to run commands on your remote server, in my case a Raspberry Pi (Linux Raspbian), using Telegram.
In fact, you will create your own Telegram Bot, and you'll be able to run commands and scripts on/from your server via this script.

### What is this repository for? ###

* Telegram Bot
* Version 4.0

#### What has been added in version 4.0?
* Python isolation installation instructions - to follow best practises.
* Reworked the script to use the most recent and supported python library `python-telegram-bot`.
* Updated the startup oneliner to reflect the changes of running the script in isolation.  

#### What has been added in version 3.0?
* New `exec` function that allows you to pass a full shell command via Telegram bot. This is a very DANGEROUS risk that can DESTROY your server and setup completely. However, in case of emergencies, it can save you. Use it wisely. And yes, they will run as `root`!
* Random generated password, required to run any command issued via `exec` function. This is a way to be sure you're the one running the command.
* 3 attempts before the password expires.
* Password sent via email (this needs to be configured in the `config.py` script)

NOTE: the `exec` function works ONLY if you set the script to send you the password via email. The script requires SMTP, username and password to send the email, and of course, the recipient who's going to receive the email. Without the password, no `exec` commands can be executed.

### How do I get set up? ###

* Clone the repository
* Make sure Python 3.11+ is installed
* Make sure the Debian/Linux package `logger` is installed too (if you use the custom startup script that logs automatically)
* Create a Python virtual environment (recommended for isolation):
    ```bash
    python3 -m venv telegram_bot
    source telegram_bot/bin/activate
    ```
* Install dependencies using `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```
* Copy `config.py.template` to `config.py` and follow the instructions to fill up the variables
* Edit `telegrambot.py` accordingly: this is the main file where you can set all your actions. Mine is an example.
* Test running `python telegrambot.py`

> NOTE: This script uses the `python-telegram-bot` library with asynchronous functions. On environments like Raspberry Pi OS, you may encounter issues with `asyncio` due to already running event loops. This is automatically handled using `nest_asyncio`.

#### Notes
My `telegrambot.py` script is a combination of OS commands and custom scripts called by this bot. You can use the same combination. What is easy to do with few _words_ is probably worth leaving as it is, but when you need to do something more complex (e.g. ssh into another server and run a command) just create your own script and call it within this bot.
Don't forget that ALL THE BOT COMMANDS, if they require root privileges, have to be properly set in the `sudoers` file.

Example:
```
myuser ALL=(ALL) NOPASSWD:/sbin/reboot
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/restart_device
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/manage_kodi
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/upgrade_raspbxino
myuser ALL=(ALL) NOPASSWD:/bin/systemctl restart openvpn.service
myuser ALL=(ALL) NOPASSWD:/tmp/temp-telegram-script.sh
```

I have custom scripts in `/usr/local/bin` and those scripts require root privileges.
I can call those scripts via my bot, but the
user `myuser` (the one who is running this Telegram bot script) has to be properly configured to grant those privileges when running the script.

**Don't forget this step** ;-)

#### If you want to automate the startup of the script

* Edit the `telegrambot_start` script with the full path and move that file into `/usr/local/bin`
* Check `rc.local`, update accordingly and add those lines into your `/etc/rc.local` script to make sure the script runs at startup

#### Optional

You can find `check_telegrambot` and `check_telegrambot_connection` files.
These are files that can be used with Nagios to monitor this script.

