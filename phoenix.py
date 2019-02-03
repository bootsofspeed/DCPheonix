import datetime
import os
import time
from random import shuffle
from requests import session

import vpn
import dc_api

SECOND = 1
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR

WAITING_TIME_FOR_TARGET_DOC = 10 * MINUTE
##

def get_now_time():
    now = datetime.datetime.now()
    now_date = now.strftime('%H:%M:%S')
    return now_date

def tprint(text, **vals):
    txt = '[{}]'.format(get_now_time()) + str(text)
    print(txt, **vals)

##

def load_ids(id_file='./ids.txt', option=None):
    if not os.path.isfile(id_file):
        return False
    id_list = []
    with open(id_file, 'r') as file:
        for raw in file.readlines():
            user_id, user_pw, id_type = raw.split(' ')
            id_list.append((user_id, user_pw, id_type))

    if option is None:
        pass
    elif option == 'shuffle':
        shuffle(id_list)
    elif option == 'fixed':
        id_list = [_id for _id in id_list if _id[-1] == 'f']
    elif option == 'non-fixed':
        id_list = [_id for _id in id_list if _id[-1] == 'n']

    return id_list

def save_used_info(gid, doc_no, used_id, vpn_data):
    vpn_name = vpn_data[vpn.HOST_NAME]
    path = './{}'.format(gid)
    file = path + '/{}'.format(doc_no)
    info = '{}, {}'.format(used_id, vpn_name)
    if not os.path.isdir(path):
        os.mkdir(path)
    with open(file, 'a') as info_file:
        info_file.write(info)
        info_file.write('\n')

def read_used_info(gid, doc_nos):
    info = {}
    for doc_no in doc_nos:
        info[doc_no] = _read_used_info(gid, doc_no)
    return info

def _read_used_info(gid, doc_no):
    path = './{}'.format(gid)
    file = path + '/{}'.format(doc_no)
    info = {'user_id': set(), 'vpn_name': set()}
    if not os.path.isdir(path):
        return False
    if not os.path.isfile(file):
        return False

    with open(file, 'r') as info_file:
        for line in info_file.readlines():
            line = line.splitlines()[0]
            user_id, vpn_name = line.split(', ')
            info['user_id'].add(user_id)
            info['vpn_name'].add(vpn_name)
    return info

class VpnCluster:
    def __init__(self, vpn_list):
        self.data = vpn_list
        self.temp_data = self.data.copy()

    def refresh(self, num):
        if self.data is None:
            self.data = vpn.get_vpn_list()
        elif len(self.data) < num:
            self.data = vpn.get_vpn_list()

        self.temp_data = self.data.copy()

    def pop(self):
        vpn_data = self.temp_data.pop()
        return vpn_data

    def index(self, vpn_data):
        idx = self.data.index(vpn_data)
        return idx

    def update(self, used_info):
        if not used_info:
            pass
        else:
            vpn_names = set()
            for name_set in used_info.values():
                vpn_names.update(name_set)
            filtered_vpn = [
                vpn_data for vpn_data in self.data if vpn_data[vpn.HOST_NAME] not in vpn_names
                ]
            self.temp_data = filtered_vpn

def phoenix(gid, doc_nos, ids, vpn_cluster):
    for dc_id, dc_pw, _ in ids:
        res = None
        while not res: #게시글이 여러 개인이상 바꿀 필요 있음
            if not vpn_cluster.temp_data:
                break
            vpn_data = vpn_cluster.pop()
            vpn_info = vpn.get_info(vpn_data)
            vpn.print_info(vpn_data)
            tprint('vpn starts to connect')
            vpn_info = vpn.start(vpn_info)

            if vpn_info['status'] == vpn.VPN_CONNECTION_FAILURE:
                vpn_cluster.data.remove(vpn_data)
                vpn.stop(vpn_info)
                tprint('vpn connecting fails.')
                continue
            elif vpn_info['status'] == vpn.VPN_CONNECTION_TIME_OUT:
                vpn_cluster.data.remove(vpn_data)
                vpn.stop(vpn_info)
                tprint('vpn connecting time out.')
                continue
            elif vpn_info['status'] == vpn.VPN_CONNECTION_SUCCESS:
                with session() as sess:
                    sess = dc_api.login(dc_id, dc_pw, sess)
                    tprint('{} login'.format(dc_id))
                    for doc_no in doc_nos:
                        try:
                            res = dc_api.upvote(gid, doc_no, sess)
                            tprint('{} of {}, {} upvoting has done.'.format(doc_no, gid, dc_id))
                        except ValueError: #when doc is removed, occured
                            dc_api.logout(sess)
                            return vpn_cluster
                        save_used_info(gid, doc_no, dc_id, vpn_data)
                    dc_api.logout(sess)
        vpn.stop(vpn_info)
    return vpn_cluster

class Command:
    def __init__(self):
        self.vpn_list = None
        self.vpn_cluster = None
        self.vpn_time = None
        self.board = None
        self.minor = None
        self.refresh(1000)

    def _add_setting(self, key, value):
        setattr(self, key, value)

    def _sub_setting(self, key):
        setattr(self, key, None)

    def is_setting_command(self, line):
        if line.startswith('+'):
            return True
        elif line.startswith('-'):
            return True
        else:
            return False

    def set(self, line):
        func = None
        if line.startswith('+'):
            argvs = line[1:].split('=')
            if argvs[0] == 'minor':
                argvs[1] = True if argvs[1] == 'True' else False
            func = self._add_setting
        elif line.startswith('-'):
            argvs = (line[1:], )
            func = self._sub_setting

        func(*argvs)
        tprint('changed setting')

    def refresh(self, num):
        if self.vpn_list is None:
            self.vpn_list = vpn.get_vpn_list()
            self.vpn_cluster = VpnCluster(self.vpn_list)
        else:
            self.vpn_cluster.refresh(num)
            self.vpn_list = self.vpn_cluster.data.copy()

        if self.vpn_time is None:
            self.vpn_time = time.time()
        else:
            if time.time() - self.vpn_time > 60 * 60:
                self.vpn_time = time.time()
                self.vpn_list = None

    def command(self):
        tprint('vpn: {}, board: {}, minor: {}'.format(
            len(self.vpn_list), self.board, self.minor
            ))
        tprint('wating for command...')
        line = input('command :')
        if self.is_setting_command(line):
            self.set(line)
        else:
            if line.startswith('do'):
                argvs = line.split()[1:]
                self.do(*argvs)
                tprint('done')
            elif line.startswith('target'):
                argvs = line.split()[1:]
                self.target(*argvs)
            else:
                tprint('wrong command')

    def target(self, *argv):
        key, value = argv[0].split('=')
        #key, value = 'title', 'ㅇㅇ' #test
        num = int(argv[-1])
        ids = load_ids(option='shuffle')[:num]

        tprint('finding target... {}-{}'.format(key, value))
        docs = dc_api.get_pages_docs(self.board, self.minor)
        docs = dc_api.refine_pages_docs(docs)

        target_docs = dc_api.find_values(docs, key, value)
        last_no = docs[0]['no']

        while True:
            if not docs or not target_docs:
                pass
            else:
                last_no = docs[0]['no']
                tprint('target has found.')
                for doc in target_docs:
                    tprint('title - {}'.format(doc['title']))
                doc_nos = dc_api.extract_values(target_docs, 'no')[::-1]
                self.vpn_cluster = phoenix(self.board, doc_nos, ids, self.vpn_cluster)
                self.vpn_cluster.refresh(int(num*1.5))

            tprint('waiting for target....')
            time.sleep(WAITING_TIME_FOR_TARGET_DOC)
            docs = dc_api.get_docs_till_find_no(self.board, self.minor, last_no)
            target_docs = dc_api.find_values(docs, key, value)

    def do(self, *argv):
        gid, num = self.board, 0

        if gid is None:
            gid = argv[0]
            doc_nos = argv[1:-1]
        else:
            doc_nos = argv[:-1]

        num = int(argv[-1])
        used_info = read_used_info(gid, doc_nos)
        self.refresh(int(num*1.5))
        self.vpn_cluster.update(used_info)
        #if len(doc_no) == 1:
        self.vpn_cluster = phoenix(gid, doc_nos, load_ids()[:num], self.vpn_cluster)
        #else:
        #    self.vpn_list = multi_phoenix(board, is_miner, doc_no, recommand=num, ids=loadIds())

if __name__ == '__main__':
    com = Command()
    while True:
        com.command()
