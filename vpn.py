import base64
import datetime
import os
import subprocess
import tempfile

import timeout_decorator
from requests import get


VPN_KILL_DELAY = 0.001
VPN_CONNECTING_TIME_LIMIT = 60


HOST_NAME, IP, SCORE, PING = 0, 1, 2, 3
SPEED, COUNTRY_LONG, COUNTRY_SHORT = 4, 5, 6
SESSIONS, UPTIME, TOTAL_TRAFFIC = 7, 8, 9
LOG_TYPE, OPERATOR, MESSAGE = 10, 11, 12
CONFIG_DATA = -1

VPN_CONNECTION_SUCCESS = 0
VPN_CONNECTION_TIME_OUT = 1
VPN_CONNECTION_FAILURE = 2

VPN_INDICES = {
    'HostName':0, 'IP':1, 'Score':2, 'Ping':3, 'Speed':4,
    'CountryLong':5, 'CountryShort':6, 'NumVpnSessions':7,
    'Uptime':8, 'TotalTraffic':9, 'LogType':10, 'Operator':11,
    'Message':12, 'config_data':-1,
    }

def filter_vpn(vpn_list, key, reverse=False):
    index = VPN_INDICES[key]
    vpn_list = [filtered for filtered in vpn_list if filtered[index].isnumeric()]
    if key == 'Ping': #None value가 가능한 vpn 정보들
        temp = []
        non_keys = [i for i in vpn_list if not i[index].isnumeric()]
        num_keys = [i for i in vpn_list if i[index].isnumeric()]
        num_keys.sort(key=lambda x:int(x[index]), reverse=reverse)
        if reverse:
            temp.extend(num_keys)
            temp.extend(non_keys)
        else:
            temp.extend(non_keys)
            temp.extend(num_keys)
        return temp
    else:
        vpn_list.sort(key=lambda x:int(x[index]), reverse=reverse)
    return vpn_list

def refine_vpn_data(raw_data):
    refined = []
    for vpn_data in raw_data.splitlines()[2:]:
        raw_line = vpn_data.split(',')
        if len(raw_line) > 1:
            refined_data = raw_line
            refined.append(refined_data)
    return refined

def get_vpn_list(country_keyword="Korea"):
    raw_data = get('http://www.vpngate.net/api/iphone/').text
    lines = refine_vpn_data(raw_data)
    if country_keyword:
        filtered = [i for i in lines if len(i)>1 and country_keyword in i[COUNTRY_SHORT if len(country_keyword)==2 else COUNTRY_LONG]]
        filtered = filter_vpn(filtered, 'Ping')
        return filtered
    else:
        return [i for i in list(lines)[2:] if len(i) > 1]

def print_info(vpn_data):
    ip, ping, sess_num = vpn_data[IP], vpn_data[PING], vpn_data[SESSIONS]
    tprint('ip: {}, ping: {}, sess: {}'.format(ip, ping, sess_num))

def get_info(vpn_data):
    config_data = vpn_data[CONFIG_DATA]
    handler, temp_path = tempfile.mkstemp()
    with open(temp_path, 'w') as f:
        f.write(base64.b64decode(config_data).decode("utf-8"))
        f.write('\nscript-security 2\nup /etc/openvpn/update-resolv-conf\ndown /etc/openvpn/update-resolv-conf\ndown-pre')

    vpn_info = {
        'subprocess': None,
        'handler': handler,
        'path': temp_path,
        'status': None,
        }

    return vpn_info

def start(vpn_info):
    func = timeout_func(_start, VPN_CONNECTING_TIME_LIMIT)
    try:
        ret = func(vpn_info)
    except timeout_decorator.timeout_decorator.TimeoutError:
        vpn_info['status'] = VPN_CONNECTION_TIME_OUT
        ret = vpn_info
    except Exception: 
        #!!timeout_decorator.timeout_decorator.TimeoutError: 'Timed Out'
        vpn_info['status'] = VPN_CONNECTION_TIME_OUT
        ret = vpn_info
    return ret

def _start(vpn_info):
    vpn_info['subprocess'] = subprocess.Popen(
        ['sudo', 'openvpn', '--config', vpn_info['path']], stdout=subprocess.PIPE, universal_newlines=True
        )

    for stdout_line in iter(vpn_info['subprocess'].stdout.readline, ""):
        if "Initialization Sequence Completed" in stdout_line:
            break
        elif "will try again" in stdout_line or "process restarting" in stdout_line:
            vpn_info['status'] = VPN_CONNECTION_FAILURE
            return vpn_info
        else:
            pass
    vpn_info['status'] = VPN_CONNECTION_SUCCESS
    return vpn_info


def stop(vpn_info):
    try:
        os.close(vpn_info['handler'])
        os.remove(vpn_info['path'])
    except OSError as oserror:
        tprint(oserror)

    os.system('sudo killall openvpn')
    while vpn_info['subprocess'].poll() is None:
        os.system('sudo killall openvpn')


###
def get_now_time():
    now = datetime.datetime.now()
    now_date = now.strftime('%H:%M:%S')
    return now_date

def tprint(text, **vals):
    txt = '[{}]'.format(get_now_time()) + str(text)
    print(txt, **vals)

def timeout_func(func, seconds):
    @timeout_decorator.timeout(seconds)
    def timed_func(*args, **kwargs):
        return func(*args, **kwargs)
    return timed_func
