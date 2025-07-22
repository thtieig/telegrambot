# Telegram Assistant

This is a Python script that allows you to run commands on your remote server, in my case a Raspberry Pi (Linux Raspbian), using Telegram.
In fact, you will create your own Telegram Bot, and you'll be able to run commands and scripts on/from your server via this script.

### What is this repository for?

* Telegram Bot
* Version 4.2

#### What has been added in version 4.2?

* **New URL fetch feature**: You can send `url <https://...>` (or just a bare link) to the bot, and it will fetch the page and return cleaned plain text.
* Updated `requirements.txt` to include `requests`, `beautifulsoup4` and optionally `lxml` and `readability-lxml` for better parsing.

#### What has been added in version 4.1?

* Minor improvements and stability fixes.

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

### How do I get set up?

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

  > **Note:** `lxml` and `readability-lxml` are optional but recommended for better URL parsing. On Raspberry Pi or Debian, you may need additional system packages:

  ```bash
  sudo apt update
  sudo apt install -y python3-dev build-essential libxml2-dev libxslt1-dev zlib1g-dev
  ```

  If compilation is slow or fails, you can comment these optional lines in `requirements.txt`.

* Copy `config.py.template` to `config.py` and follow the instructions to fill up the variables

* Edit `telegrambot.py` accordingly: this is the main file where you can set all your actions. Mine is an example.

* Test running `python telegrambot.py`

> NOTE: This script uses the `python-telegram-bot` library with asynchronous functions. On environments like Raspberry Pi OS, you may encounter issues with `asyncio` due to already running event loops. This is automatically handled using `nest_asyncio`.

#### Notes

My `telegrambot.py` script is a combination of OS commands and custom scripts called by this bot. You can use the same combination. What is easy to do with few *words* is probably worth leaving as it is, but when you need to do something more complex (e.g. ssh into another server and run a command) just create your own script and call it within this bot.
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

#### Scripts in utils folder

In the folder `utils` you can find some scripts that could be handy to automate some functions like autostart at boot, monitoring checks etc.In the folder `utils` you can find some scripts that could be handy to automate some functions like autostart at boot, monitoring checks etc.

The scripts require some changes/updates and modifications before being fully functional: make sure to EDIT/UPDATE them before installing them.

Here the list of the files:

* telegrambot\_start.example: this script can be used to automatically start your bot using the suggested Python custom environment. Ideally copied in `/usr/local/bin/telegrambot_start`. Make sure to `chmod +x` the file and to update the file using the right path/username.
* check\_telegrambot\_connection.monit-check: this script can be used with Monit to verify if the bot is running. Ideally copied in `/usr/local/bin/check_telegrambot_connection`. Make sure to `chmod +x` the file.
* telegrambot.monit-config: this is a sample of Monit config file. You can copy it in `/etc/monit/conf-available/telegram_bot` (make sure to update the script with the right user) and enable it, as per Monit's instructions.
* rc.local.append: you can append the content of this file to your `rc.local` file to automatically start the script at boot. Make sure to update it with the actual user that's going to run the Telegram bot script BEFORE appending to `rc.local`.
* check\_telegrambot.nagios: This is an old script for Nagios. I'm NO LONGER maintaining it, but you can use it as example.

## License

---

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

