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

