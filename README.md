# README #

This is a python script that allows you to run commands on your remote server, in my case a Raspberry Pi (Linux raspbian), using Telegram.
In fact, you will create your own Telegram Bot, and you'll be able to run commands and scripts on/from your server via this script.

### What is this repository for? ###

* Telegram Bot
* version 3.0

#### What has been added in version 3.0?
* New `exec` function that allows you to pass a full shell command via Telegram bot. This is a very DANGEROUS risk than can DESTROY completely your server and setup. However, in case of emergencies, it can save you. Use it wisely. And yes, they will run as `root`!
* Random generated password, required to run any command issued via `exec` fuction. This is a way to be sure you're the one running the command.  
* 3 attempts before the password expires. 
* Password sent via email (this needs to be configured in the `config.py` script)

NOTE: the `exec` function works ONLY if you set the script to send you the password via email. The script requires smtp, username and password to send the email, and of course, the recepient who's going to receive the email. Without the password, no `exec` commands can be executed.

### How do I get set up? ###

* Clone the repository
* Make sure Python and the package `logger` are installed
* Copy `config.py.template` to `config.py` and follow the instructions to fill up the variables
* Edit `telegrambot.py` accordingly: this is the main file where you can set all your actions. Mine is an example.
* Test running `python telegram.py`

#### Notes
My `telegrambot.py` script is a combination of OS commands and custom scripts called by this bot. You can use the same combination. What is easy to do with few _words_ is probably worth leaving as it is, but when you need to do something more complex (e.g. ssh into another server and run a command) just create your own script and call it within this bot.  
Don't forget that ALL THE BOT COMMANDS, if they require root privileges, ALL they have to be properly set in `sudoers` file.

Example:
```
myuser ALL=(ALL) NOPASSWD:/sbin/reboot
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/restart_device
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/manage_kodi
myuser ALL=(ALL) NOPASSWD:/usr/local/bin/upgrade_raspbxino
myuser ALL=(ALL) NOPASSWD:/bin/systemctl restart openvpn.service
myuser ALL=(ALL) NOPASSWD:/tmp/temp-telegram-script.sh
```

I have custom scripts into `/usr/local/bin` and those scripts require root privileges.  
I can call those scripts via my bot, but the
user `myuser` (the one is running this Telegram bot script) has to be set properly to grant those privileges when running the script.  

**Don't forget this step** ;-)


#### If you want to automate the startup of the script

* Edit `telegrambot_start` script with the full path and move that file into `/usr/local/bin`
* Check `rc.local`, update accordingly and add those lines into your `/etc/rc.local` script, to make sure the script runs at startup

#### Optional

You can find `check_telegrambot` and `check_telegrambot_connection` files.
These are files that can be used with Nagios to monitor this script.


