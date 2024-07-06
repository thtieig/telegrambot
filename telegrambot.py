import os, subprocess, time
import telepot
from config import id_a, username, bot_token

bot = telepot.Bot(bot_token)

# Send a startup message
startup_chat_id = id_a[0]  # Replace with your chat/phone ID if different
bot.sendMessage(startup_chat_id, "Hey, just woke up man!")

def execute_command(command_list):
    try:
        result = subprocess.check_output(command_list).decode('utf-8')
    except subprocess.CalledProcessError as e:
        result = str(e)
    return result

def handle(msg):
    chat_id = msg['chat']['id']
    command = msg['text']
    sender = msg['from']['id']
    isbot = msg['from']['is_bot']
    user = msg['from']['username']
    print('Got command: %s' % command)

    if sender in id_a and not isbot and user in username:
        command_dict = {
            'uptime': ['uptime'],
            'df': ['df', '-h'],
            'last': ['last'],
            'vpn-restart': ['sudo', 'systemctl', 'restart', 'openvpn.service'],
            'kodi stop': ['sudo', 'manage_kodi', 'off'],
            'kodi start': ['sudo', 'manage_kodi', 'on'],
            'upgrade raspbxino': ['sudo', 'upgrade_raspbxino'],
            'tunnel-ssh': ['/usr/local/bin/ssh-port-forward.sh']
        }

        if command in command_dict:
            result = execute_command(command_dict[command])
            bot.sendMessage(chat_id, result)
        elif command.startswith('restart'):
            cmd = command.split('restart', 1)[1].strip()
            device_dict = {
                'router': ['sudo', 'restart_device', 'router'],
                'raspberrino': ['sudo', 'restart_device', 'raspberrino'],
                'raspbxino': ['sudo', 'restart_device', 'raspbxino']
            }

            if cmd in device_dict:
                result = execute_command(device_dict[cmd])
                bot.sendMessage(chat_id, result)
            else:
                msg = 'Usage: restart (router|raspberrino|raspbxino)'
                bot.sendMessage(chat_id, msg)
        else:
            msg = 'Commands available:\n' + '\n'.join(command_dict.keys()) + '\nrestart <device>'
            bot.sendMessage(chat_id, msg)
    else:
        bot.sendMessage(chat_id, 'Forbidden access!')

bot.message_loop(handle)
print('I am listening...')

while 1:
    try:
        time.sleep(10)
    except KeyboardInterrupt:
        print('\n Program interrupted')
        exit()
    except Exception as e:
        print('Other error or exception occurred:', e)

