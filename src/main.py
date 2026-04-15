import base64
import datetime
import json
import os
import time
import webbrowser

import discord_webhook
import pytz
import requests


AUTH_BASE_URL          = 'https://accounts.spotify.com/api'
AUTH_CONTENT_TYPE      = 'application/x-www-form-urlencoded'
BASE_CONFIG            = { 'client_id': '', 'client_secret': '', 'webhook_url': '' }
BASE_URL               = 'https://api.spotify.com/v1'
CODE_GOOD              = 200
CODE_CREATED           = 201
CODE_ACCEPTED          = 202
CODE_NO_CONTENT        = 204
CODE_NOT_MODIFIED      = 304
CODE_BAD_REQUEST       = 400
CODE_UNAUTHORIZED      = 401
CODE_FORBIDDEN         = 403
CODE_NOT_FOUND         = 404
CODE_TOO_MANY_REQUESTS = 429
CODE_INTERNAL_ERROR    = 500
CODE_BAD_GATEWAY       = 502
CODE_UNAVAILABLE       = 503
PERMISSIONS            = ('user-modify-playback-state', 'user-read-playback-state')
REDIRECT_URI           = 'http://127.0.0.1:7777/callback'
SCRIPT_DIR             = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTH_FILE              = os.path.join(SCRIPT_DIR, 'auth.json')
CONFIG_FILE            = os.path.join(SCRIPT_DIR, 'config.json')
LOG_FILE               = os.path.join(SCRIPT_DIR, 'log.log')

active_device = ''
auth          = {}
auth_code     = ''
config        = {}
last_device   = ''


def disable_shuffle() -> bool:
    global auth

    req = requests.put(
        f'{BASE_URL}/me/player/shuffle?state=false',
        headers={
            'Authorization': auth['access']
        }
    )

    if req.status_code != CODE_GOOD:
        log(f'failed to disable shuffle ({req.status_code}): {req.text}')
        return False

    log('disabled shuffle')

    return True


def discord_notify(msg: str | Exception) -> None:
    global config

    log(msg)

    if 'webhook_url' in config:
        webhook = discord_webhook.DiscordWebhook(config['webhook_url'])
        webhook.add_embed(discord_webhook.DiscordEmbed('spotify-shuffler', msg))
        webhook.execute()


def enable_shuffle() -> bool:
    global auth

    req = requests.put(
        f'{BASE_URL}/me/player/shuffle?state=true',
        headers={
            'Authorization': auth['access']
        }
    )

    if req.status_code != CODE_GOOD:
        log(f'failed to enable shuffle ({req.status_code}): {req.text}')
        return False

    log('enabled shuffle')

    return True


def generate_config() -> bool:
    log('generating config')

    try:
        with open(CONFIG_FILE, 'w', newline='\n') as f:
            json.dump(BASE_CONFIG, f, indent=4, sort_keys=True)
            return True

    except Exception:
        return False


def get_auth() -> bool:
    global auth

    req = requests.post(
        f'{AUTH_BASE_URL}/token'
            + '?grant_type=authorization_code'
            + f'&code={auth_code}'
            + f'&redirect_uri={REDIRECT_URI}',
        headers={
            'Authorization': auth['basic'],
            'Content-Type': AUTH_CONTENT_TYPE
        }
    )

    if req.status_code != CODE_GOOD:
        log(f'failed getting auth ({req.status_code}): {req.text}')
        return False

    try:
        data = req.json()
        auth['access'] = f'{data['token_type']} {data['access_token']}'
        auth['refresh'] = data['refresh_token']
        log('got auth')
        return True

    except Exception as e:
        log(f'failed getting auth: {e}')
        return False


def get_auth_code() -> bool:
    global auth_code
    global config

    webbrowser.open(
        'https://accounts.spotify.com/authorize'
            + f'?client_id={config['client_id']}'
            + '&response_type=code'
            + f'&redirect_uri={REDIRECT_URI}'
            + f'&scope={' '.join(PERMISSIONS)}'
    )

    try:
        auth_code = input('callback URL: ').split('?code=')[1]
    except Exception:
        pass

    return len(auth_code) > 0


def get_playback_state() -> bool:
    global active_device
    global auth
    global last_device

    req = requests.get(
        f'{BASE_URL}/me/player',
        headers={
            'Authorization': auth['access']
        }
    )

    if req.status_code != CODE_GOOD:
        if req.status_code != CODE_NO_CONTENT:
            log(f'failed to get playback state ({req.status_code}): {req.text}')

            if req.status_code == CODE_UNAUTHORIZED:
                refresh_auth()

        active_device = ''

        if last_device:
            log(f'device lost (was {last_device})')

        last_device = ''

        return False

    try:
        data = req.json()
        active_device = data['device']['name']
        if last_device != active_device:
            handle_new_device()
        return True

    except Exception as e:
        log(f'failed to get playback state: {e}')
        return False


def handle_new_device():
    global active_device
    global auth
    global last_device

    log(f'new device: {active_device} (was {last_device if last_device else '<none>'})')

    last_device = active_device

    disable_shuffle()
    enable_shuffle()


def load_auth() -> bool:
    global auth

    try:
        with open(AUTH_FILE) as f:
            auth = json.load(f)

            return all((
                'access' in auth,
                'basic' in auth,
                'refresh' in auth
            ))

    except Exception:
        return False


def load_config() -> bool:
    global config

    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)

            return all((
                'client_id' in config,
                len(config['client_id']) == 32,
                'client_secret' in config,
                len(config['client_secret']) == 32
            ))

    except Exception:
        return False


def log(msg: str) -> None:
    utc = datetime.datetime.now(pytz.timezone('UTC')).strftime(f'%Y-%m-%d %H:%M:%S.%f')[:-3]
    denver = f'Denver {datetime.datetime.now(pytz.timezone('America/Denver')).strftime('%H:%M')}'
    text = f'[{utc} ({denver})] {msg}'

    print(text)

    with open(LOG_FILE, 'a', newline='\n') as f:
        f.write(f'{text.encode('unicode-escape').decode('ascii')}\n')


def refresh_auth() -> bool:
    global auth

    log('refreshing token')

    req = requests.post(
        f'{AUTH_BASE_URL}/token'
            + '?grant_type=refresh_token'
            + f'&refresh_token={auth['refresh']}',
        headers={
            'Authorization': auth['basic'],
            'Content-Type': AUTH_CONTENT_TYPE
        }
    )

    if req.status_code != CODE_GOOD:
        log(f'failed to refresh token ({req.status_code}): {req.text}')
        return False

    try:
        data = req.json()
        auth['access'] = f'{data['token_type']} {data['access_token']}'
        log('refreshed auth')

        if not save_auth():
            log('failed to save auth')
            return False

        return True

    except Exception as e:
        log(f'failed to refresh token: {e}')
        return False


def save_auth() -> bool:
    global auth

    try:
        with open(AUTH_FILE, 'w', newline='\n') as f:
            json.dump(auth, f, indent=4, sort_keys=True)
            return True

    except Exception:
        return False


def main() -> None:
    try:
        if not load_config():
            generate_config()
            raise Exception('blank config')

        if not load_auth():
            log('getting auth')

            auth['basic'] = f'Basic {base64.b64encode(f'{config['client_id']}:{config['client_secret']}'.encode()).decode()}'

            if not get_auth_code():
                raise Exception('missing auth code')

            if not get_auth():
                raise Exception('failed to get auth')

            if not save_auth():
                raise Exception('failed to save auth')

        log('loaded auth')

        while True:
            get_playback_state()
            time.sleep(5.0)

    except Exception as e:
        discord_notify(e)

    finally:
        discord_notify('loop broke')


if __name__ == '__main__':
    main()
