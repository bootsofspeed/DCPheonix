import time
from datetime import datetime

import lxml
import requests
import timeout_decorator
from bs4 import BeautifulSoup

GET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Mobile Safari/537.36",
    "Upgrade-Insecure-Requests": "1",
    "Host": "m.dcinside.com",
    "Connection": "keep-alive",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"
    }

POST_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Host": "m.dcinside.com",
    "Origin": "http://m.dcinside.com",
    "Referer": "http://m.dcinside.com/write.php?id=alphago&mode=write",
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Mobile Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    }

DELAY_TIME = 0.1 #second
UPVOTE_PROCESS_TIMEOUT = 60
UPVOTE_TIMEOUT = 15
UPVOTE_WHOLE_PROCESS_TIMEOUT = 120

def _post(sess, url, data=None, json=None, **kwargs):
    res = None
    while not res:
        try:
            res = sess.post(url, data=data, json=json, **kwargs)
            break
        except requests.exceptions.Timeout as error:
            tprint('requests post timed out.')
            tprint(error)
        except requests.exceptions.RequestException as error:
            tprint('requests post occur error.')
            tprint(error)
        finally:
            time.sleep(DELAY_TIME)
        #except Exception as e:
        # ConnectionError
        # HTTPError
        # TooManyRedirects
        # ConnectTimeout
    return res

def _get(sess, url, **kwargs):
    res = None
    while not res:
        try:
            res = sess.get(url, **kwargs)
            break
        except requests.exceptions.Timeout as error:
            tprint('requests get timed out.')
            tprint(error)
        except requests.exceptions.RequestException as error:
            tprint('requests get occur error.')
            tprint(error)
        finally:
            time.sleep(DELAY_TIME)
        #except Exception as e:
        #    print('unexpected error occur')
        #    print(e)
        #    res = None
    return res

def iterableBoard(board, is_miner=False, num=-1, start_page=1, sess=None):
    # create session
    if sess is None:
        sess = requests.session()
    url = "http://m.dcinside.com/list.php"
    params = { "id": board, "page": str(start_page) }
    i = 0
    last_doc_no = 0
    doc_in_page = 0
    page = start_page
    header = GET_HEADERS.copy()
    header["Referer"] = url
    while num != 0:
        params["page"] = str(page)
        res = _get(sess, url, headers=header, params=params, timeout=3)
        t, start = raw_parse(res.text, '"list_best">', "<", i)
        t, end = raw_parse(res.text, "</ul", ">", start)
        i = start
        while num != 0 and i < end and i >= start:
            doc_no, i = raw_parse(res.text, 'no=', '&', i)
            if i >= end or i == 0:
                break
            doc_no = int(doc_no)
            if last_doc_no != 0 and doc_no >= last_doc_no:
                continue
            #nick_mnr_comm ic_sc_m : 파딱
            last_doc_no = doc_no
            t, i = raw_parse(res.text, 'ico_pic ', '"', i)
            has_image = (t == "ico_p_y")
            title, i = raw_parse(res.text, 'txt">', '<', i)
            t, i = raw_parse(res.text, 'txt_num">', "<", i)
            comments = t[1:-1] if len(t)>0 else "0"
            name, i = raw_parse(res.text, 'name">', "<", i)
            t, i = raw_parse(res.text, 'class="', '"', i)
            ip = None
            if t == "userip":
                ip, i = raw_parse(res.text, '>', '<', i) 
            date, i = raw_parse(res.text, "<span>", "<", i)
            t, i = raw_parse(res.text, '조회', '<', i)
            views, i = raw_parse(res.text, '>', '<', i)
            t, i = raw_parse(res.text, '추천', "<", i)
            votes, i = raw_parse(res.text, '>', '<', i)
            if "/" in comments: comments = sum((int(z) for z in comments.split("/")))
            if "/" in votes: votes = sum(int(z) for z in votes.split("/"))
            yield {
                "doc_no": doc_no, "title": title, "name": name, "ip": ip, "date": date,
                "views": int(views), "votes": int(votes), "comments": int(comments),
                }
            num -= 1
        page += 1

def iterableComments(board, is_miner, doc_no, num=-1, sess=None):
    if sess is None:
        sess = requests.session()
    referer = "http://m.dcinside.com/view.php?id=%s&no=%s" % (board, doc_no)
    url = "http://m.dcinside.com/%s/comment_more_new.php" % ("m" if is_miner else "")
    page = 1
    params = {"id": board, "no": str(doc_no), "com_page": str(page), "write": "write"}
    headers = GET_HEADERS.copy()
    headers["Referer"] = referer
    headers["Accept-Language"] = "en-US,en;q=0.9"
    num_comments, i, count = 999999999,0,0

    while num != 0:
        params["com_page"] = str(page)
        res = _get(sess, url, headers=headers, params=params, timeout=3)
        t, i = raw_parse(res.text, 'txt_total">(', ')', i)
        if i==0: break
        num_comments = min(num_comments, int(t))
        i = -1
        while num != 0:
            date, i3 = rraw_parse(res.text, '"date">', '<', i)
            comment_no2, i2 = rraw_parse(res.text, ":del_layer('", "'", i)
            comment_no, i = rraw_parse(res.text, ":comment_del('", "'", i)
            if i==0 and i2==0 and i3==0: break
            if i<=i2<=i3: comment_no, i = None, i3
            elif i<=i3<=i2: comment_no, i = comment_no2, i2
            contents, i = rraw_parse(res.text, '"txt">', '="info">', i)
            ip, i = rraw_parse(res.text, '"ip">', '<', i)
            name, i = rraw_parse(res.text, '>[', ']<', i)
            name = name.replace('<span class="nick_comm flow"></span>', "")
            name = name.replace('<span class="nick_comm fixed"></span>', "")
            name = name.replace('<span class="nick_mnr_comm ic_gc_df"></span>', "")
            #user_id, _ = rraw_parse(res.text, 'g_id=', '" class=', i)
            yield {
                "name": name.strip(), "comment_no": comment_no, "ip": ip.strip(),
                "contents": contents[:-66].strip(), "date": date.strip()
                }
                #"user_id": user_id.strip()}
            num -= 1
            count += 1
        if count >= num_comments:
            break
        else:
            page += 1

def writeDoc(board, is_miner, title, contents, name=None, password=None, sess=None):
    # create session
    if sess is None:
        sess = requests.Session()
    url = "http://m.dcinside.com/write.php?id=%s&mode=write" % board
    res = _get(sess, url, headers=GET_HEADERS)
    # get secret input
    data = extractKeys(res.text, 'g_write.php"')
    if name: data['name'] = name
    if password: data['password'] = password
    data['subject'] = title
    data['memo'] = contents
    # get new block key
    headers = POST_HEADERS.copy()
    headers["Referer"] = url
    url = "http://m.dcinside.com/_option_write.php"
    
    verify_data = {
        "id": data["id"],
        "w_subject": title,
        "w_memo": contents,
        "w_filter": "",
        "mode": "write_verify",
    }
    new_block_key = _post(sess, url, data=verify_data, headers=headers).json()
    if new_block_key["msg"] != "5":
        print("Error while write doc(block_key)")
        raise Exception(repr(new_block_key))
    data["Block_key"] = new_block_key["data"]
    #print(data)
    url = "http://upload.dcinside.com/g_write.php"
    result = _post(sess, url, data=data, headers=headers).text
    doc_no, i = raw_parse(result, "no=", '"')
    if doc_no is None:
        print("Error while writing doc")
        raise Exception(repr(result))
    return doc_no

def modifyDoc(board, is_miner, doc_no, title, contents, name=None, password=None, sess=None):
    # create session
    if sess is None:
        sess = requests.Session()
    url = "http://m.dcinside.com/write.php"
    res = None
    if password:
        data = {"write_pw": password, "no": doc_no, "id": board, "mode": "modify", "page": ""}
        headers = GET_HEADERS.copy()
        headers["Referer"] = "http://m.dcinside.com/password.php?id=%s&no=%s&mode=modify" % (board, doc_no)
        headers["Origin"] = "http://m.dcinside.com"
        headers["Host"] = "m.dcinside.com"
        headers["Accept-Language"] = "en-US,en;q=0.9"
        headers["Cache-Control"] = "max-age=0"
        headers["Connection"] = "keep-alive"
        res = _post(sess, url, data=data, headers=headers)
    else:
        params = {"id": board, "no": doc_no, "mode": "modify", "page": ""}
        headers = GET_HEADERS.copy()
        headers["Referer"] = "http://m.dcinside.com/view.php?id=%s&no=%s&page=" % (board, doc_no)
        headers["Host"] = "m.dcinside.com"
        headers["Origin"] = "http://m.dcinside.com"
        headers["Accept-Language"] = "en-US,en;q=0.9"
        headers["Cache-Control"] = "max-age=0"
        headers["Connection"] = "keep-alive"
        res = _get(sess, url, params=params, headers=headers)
    data = extractKeys(res.text, 'g_write.php"')
    # get secret input
    if "id" not in data:
        print("Error while modify doc(Maybe there's no article with that id)")
        raise Exception(repr(res.text))
    if name: data['name'] = name
    if password: data['password'] = password
    data['subject'] = title
    data['memo'] = contents
    # get new block key
    headers = POST_HEADERS.copy()
    headers["Referer"] = url
    url = "http://m.dcinside.com/_option_write.php"
    verify_data = {
        "id": data["id"],
        "w_subject": title,
        "w_memo": contents,
        "w_filter": "",
        "mode": "write_verify",
    }
    new_block_key = _post(sess, url, data=verify_data, headers=headers).json()
    if new_block_key["msg"] != "5":
        print("Error while modify doc(block_key)")
        raise Exception(repr(new_block_key))
    data["Block_key"] = new_block_key["data"]
    url = "http://upload.dcinside.com/g_write.php"
    result = _post(sess, url, data=data, headers=headers).text
    doc_no, i = raw_parse(result, "no=", '"')
    if doc_no is None:
        print("Error while writing doc")
        raise Exception(repr(result))
    return doc_no

def removeDoc(board, is_miner, doc_no, password=None, sess=None):
    # create session
    if sess is None:
        sess = requests.Session()
    headers = POST_HEADERS.copy()
    data = {"no": doc_no, "id": board, "page": "", "mode": "board_del"}
    if password:
        url = "http://m.dcinside.com/_access_token.php"
        headers["Referer"] = "http://m.dcinside.com/password.php?id=%s&no=%s&mode=board_del2&flag=" % (board, doc_no)
        result = _post(sess, url, data={"token_verify": "nonuser_del"}, headers=headers).json()
        if result["msg"] != "5":
            print("Error while write doc(block_key)")
            print(result)
            raise Exception(repr(result))
        data["mode"] = "board_del2"
        data["write_pw"] = password
        data["con_key"] = result["data"]
    else:
        url = "http://m.dcinside.com/view.php?id=%s&no=%s" % (board, doc_no)
        res = _get(sess, url, headers=GET_HEADERS)
        user_no = raw_parse(res.text, '"user_no" value="', '"')[0]
        headers["Referer"] = url
        data["mode"] = "board_del"
        data["user_no"] = user_no
    url = "http://m.dcinside.com/_option_write.php"
    result = _post(sess, url, data=data, headers=headers).json()
    if (type(result)==int and result != 1) or (type(result)==dict and result["msg"] != "1"):
        print("Error while remove doc: ", result)
        raise Exception(repr(result))
    return sess

def writeComment(board, is_miner, doc_no, contents, name=None, password=None, sess=None):
    # create session
    if sess is None:
        sess = requests.Session()
    url = "http://m.dcinside.com/view.php?id=%s&no=%s" % (board, doc_no)
    res = _get(sess, url, headers=GET_HEADERS, timeout=3)
    data = extractKeys(res.text, '"comment_write"')
    if name: data["comment_nick"] = name
    if password: data["comment_pw"] = password
    data["comment_memo"] = contents
    headers = POST_HEADERS.copy()
    headers["Referer"] = url
    url = "http://m.dcinside.com/_access_token.php"
    block_key = _post(sess, url, headers=headers, data={"token_verify": "com_submit"}, timeout=3).json()
    if block_key["msg"] != "5":
        print("Error while write comment(block key)")
        raise Exception(repr(block_key))
    url = "http://m.dcinside.com/_option_write.php"
    data["con_key"] = block_key["data"]
    result = _post(sess, url, headers=headers, data=data, timeout=3)
    result = result.json()
    if (type(result)==int and result != 1) or (type(result)==dict and result["msg"] != "1"):
        print("Error while write comment", result)
        raise Exception(repr(result))
    return doc_no

def removeComment(board, is_miner, doc_no, comment_no, password=None, sess=None):
    if sess is None:
        sess = requests.Session()
    data = None
    headers = POST_HEADERS.copy()
    headers["Referer"] = "http://m.dcinside.com/view.php?id=%s&no=%s" % (board, doc_no)
    if password: 
        data = {"id": board, "no": doc_no, "iNo": comment_no, "user_no": "nonmember", "comment_pw": password, "best_chk": "", "con_key": None, "mode": "comment_del"}
        url = "http://m.dcinside.com/_access_token.php"
        block_key = _post(sess, url, headers=headers, data={"token_verify": "nonuser_com_del"}, timeout=3).json()
        if block_key["msg"] != "5":
            print("Error while remove comment(block key)")
            raise Exception(repr(block_key))
        data["con_key"] = block_key["data"]
    else:
        url = "http://m.dcinside.com/view.php?id=%s&no=%s" % (board, doc_no)
        res = _get(sess, url, headers=GET_HEADERS, timeout=3)
        board_id, i = raw_parse(res.text, '"board_id" value="', '"')
        if not board_id:
            pass
            #raise Exception("Non-password remove comment without login")
        user_no, _ = raw_parse(res.text, '"user_no" value="', '"', i)
        data = {"id": board, "no": doc_no, "iNo": comment_no, "user_no": user_no, "board_id": board_id, "best_chk": "", "mode": "comment_del"}
        #print(data)
    url = "http://m.dcinside.com/_option_write.php"
    result = _post(sess, url, headers=headers, data=data, timeout=3)
    result = result.json()
    if (type(result)==int and result != 1) or (type(result)==dict and result["msg"] != "1"):
        print("Error while write comment", result)
        raise Exception(repr(result))
    return comment_no

def login(userid, password, sess=None):
    if sess is None:
        sess = requests.Session()
    data = {}
    url = "http://m.dcinside.com/login.php?r_url=m.dcinside.com%2Findex.php"
    headers = GET_HEADERS.copy()
    headers["Referer"] = "http://m.dcinside.com/index.php"
    while 'con_key' not in data:
        res = _get(sess, url, headers=headers, timeout=3)
        data = extractKeys(res.text, '"login_process')
    headers = POST_HEADERS.copy()
    headers["Referer"] = url
    url = "http://m.dcinside.com/_access_token.php"
    res = _post(sess, url, headers=headers, data={"token_verify": "login", "con_key": data["con_key"]}, timeout=3)
    data["con_key"] = res.json()["data"]
    url = "https://dcid.dcinside.com/join/mobile_login_ok.php"
    headers["Host"] = "dcid.dcinside.com"
    headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"
    headers["Accept-Encoding"] = "gzip, deflate, br"
    headers["Cache-Control"] = "max-age=0"
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    del(headers["X-Requested-With"])
    data["user_id"] = userid
    data["user_pw"] = password
    data["id_chk"] = ""
    if "form_ipin" in data: del(data["form_ipin"])
    res = _post(sess, url, headers=headers, data=data, timeout=3)
    while 0 <= res.text.find("rucode"):
        return login(userid, password)
    return sess

def logout(sess):
    url = "http://m.dcinside.com/logout.php?r_url=m.dcinside.com%2Findex.php"
    headers = GET_HEADERS.copy()
    headers["Referer"] = "http://m.dcinside.com/index.php"
    res = _get(sess, url, headers=headers, timeout=3)
    #tprint('{} logout'.format(get_now_time(), dc_id))
    return sess
    
def extractKeys(html, start_form_keyword):
    p = ""
    start, end, i = 0, 0, 0
    result = {}
    (p, start) = raw_parse(html, start_form_keyword, '', i)
    (p, end) = raw_parse(html, '</form>', '', start)
    i = start
    while True:
        (p, i) = raw_parse(html, '<input type="hidde', '"', i)
        if not p or i >= end: break
        (name, i) = raw_parse(html, 'name="', '"', i)
        if not name or i >= end: break
        (value, i_max) = raw_parse(html, '', '>', i)
        (value, i) = raw_parse(html, 'value="', '"', i)
        if i_max > i:
            result[name] = value
        else:
            i = i_max
            result[name] = ""
    i = start
    while True:
        (p, i) = raw_parse(html, "<input type='hidde", "'", i)
        if not p or i >= end: break
        (name, i) = raw_parse(html, "name='", "'", i)
        if not name or i >= end: break
        (value, i_max) = raw_parse(html, '', '>', i)
        (value, i) = raw_parse(html, "value='", "'", i)
        if i_max > i:
            result[name] = value
        else:
            i = i_max
            result[name] = ""
    while True:
        (p, i) = raw_parse(html, '<input type="hidde', '"', i)
        if not p or i >= end: break
        (name, i) = raw_parse(html, 'NAME="', '"', i)
        if not name or i >= end: break
        (value, i_max) = raw_parse(html, '', '>', i)
        (value, i) = raw_parse(html, 'value="', '"', i)
        if i_max > i:
            result[name] = value
        else:
            i = i_max
            result[name] = ""
    return result

def rraw_parse(text, start, end, offset=0):
    s = text.rfind(start, 0, offset)
    if s == -1: return None, 0
    s += len(start)
    e = text.find(end, s)
    if e == -1: return None, 0
    return text[s:e], s - len(start)

def upvote(board, doc_no, sess=None):
    if sess is None:
        sess = requests.session()
    url = "http://m.dcinside.com/view.php?id=%s&no=%s" % (board, doc_no)
    res = _get(sess, url, headers=GET_HEADERS, timeout=3)
    if res.status_code == 404:
        return False
    #cookie_name, _ = raw_parse(res.text, 'setCookie_hk_hour("', '"', s)
    cookie_name = get_upvote_cookie_name(res.text)
    sess.cookies[cookie_name] = "done"
    data = get_upvote_data(res.text)

    headers = POST_HEADERS.copy()
    headers["Referer"] = url
    headers["Accept-Language"] = "en-US,en;q=0.9"
    url = "http://m.dcinside.com/_recommend_join.php"
    res = _post(sess, url, headers=headers, data=data, timeout=3)

    #True or False
    return ':"1"' in res.text

def get_upvote_cookie_name(text):
    _, sdx = raw_parse(text, "function join_recommend()", "{")
    cookie_name, _ = raw_parse(text, 'setCookie_hk_hour("', '"', sdx)
    #cookie_name = '{}_recomPrev_{}'.format(board, doc_no)
    return cookie_name

def get_upvote_data(text):
    _, sdx = raw_parse(text, "function join_recommend()", "{")
    _, edx = raw_parse(text, "$.ajax", "{", sdx)
    data = {}
    while sdx < edx:
        line, sdx = raw_parse(text, '= "', '"', sdx)
        if sdx >= edx:
            break
        line = line.split("=")
        #query 분리
        data[line[0] if line[0][0] != "&" else line[0][1:]] = line[1] or "undefined"
    return data


def raw_parse(text, start, end, offset=0):
    s = text.find(start, offset)
    if s == -1: return None, 0
    s += len(start)
    e = text.find(end, s)
    if e == -1: return None, 0
    return text[s:e], e
### dc_api 원본 부분


DOC_SELECTOR = 'div.gallery_list > div.list_table > table > tbody > tr'
SIMPLE_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.89 Safari/537.36"}

class GalleryInfo:
    BOARD_URL = 'http://gall.dcinside.com/{}/board/lists/'
    VIEW_URL = 'http://gall.dcinside.com/{}/board/view/'
    LOGIN_URL = 'http://dcid.dcinside.com/join/login.php?s_url=http://gall.dcinside.com'

    BOARD = 'main'
    VIEW = 'view'

    def __init__(self, gid, minor):
        self.gid = gid
        self.minor = minor

    def get_board_url(self, page):
        url = self.get_base_url(GalleryInfo.BOARD)
        param = get_params(
            {'id':self.gid, 'page': page}
            )
        return url + param

    def get_doc_url(self, doc_no):
        url = self.get_base_url(GalleryInfo.VIEW)
        param = get_params(
            {'id':self.gid, 'no': doc_no}
            )
        return url + param

    def get_base_url(self, url_type):
        gtype = 'mgallery' if self.minor else ''
        if url_type == GalleryInfo.BOARD:
            url = GalleryInfo.BOARD_URL.format(gtype)
        elif url_type == GalleryInfo.VIEW:
            url = GalleryInfo.VIEW_URL.format(gtype)
        return url

def get_params(vals):
    txt = '?'
    for key, value in vals.items():
        txt += '{}={}&'.format(key, value)
    return txt

def get_url(minor, params):
    _url = 'http://gall.dcinside.com/{}/board/{}/'
    if minor:
        url = _url.format('mgallery', 'lists')
    else:
        url = _url.format('', 'view')
        params['no'] = '1'
    param = get_params(params)

    return url + param

###################
# 0 - index
# 1 - title
# 2 - writer info
# 3 - written date
# 4 - views
# 5 - recommands
###################
def refine_doc_info(doc_soup):
    doc_info = {
        'title': None, 'no': None,
        'user_id': None, 'user_name': None,
        'ip': None, 'date': None,
        'views': None, 'recommands': None,
        }

    doc_info['title'] = get_doc_title(doc_soup)
    doc_info['no'] = get_doc_no(doc_soup)
    doc_info['user_id'] = get_doc_user_id(doc_soup)
    doc_info['user_name'] = get_doc_user_name(doc_soup)
    doc_info['ip'] = get_doc_ip(doc_soup)
    doc_info['date'] = get_doc_date(doc_soup)
    doc_info['views'] = get_doc_views(doc_soup)
    doc_info['recommands'] = get_doc_recommands(doc_soup)
    return doc_info

def get_doc_title(soup):
    target_soup = soup[1]
    title = target_soup.a.text
    return title

def get_doc_no(soup):
    target_soup = soup[1]
    href = target_soup.a.get('href')
    s = href.find('no') + 3
    e = href[s:].find('&')
    return href[s : s+e]

def get_doc_user_id(soup):
    target_soup = soup[2]
    user_id = target_soup.get('user_id')
    return user_id

def get_doc_user_name(soup):
    target_soup = soup[2]
    user_name = target_soup.get('user_name')
    return user_name

def get_doc_ip(soup):
    target_soup = soup[2]
    ip = target_soup.get('ip')
    return ip

def get_doc_date(soup):
    target_soup = soup[3]
    raw_date = target_soup.get('title')
    #date_format = '%Y.%m.%d %H:%M:%S'
    #date = datetime.strptime(raw_date, date_format)
    date = raw_date
    return date

def get_doc_views(soup):
    target_soup = soup[4]
    views = target_soup.text
    return views

def get_doc_recommands(soup):
    target_soup = soup[5]
    recommands = target_soup.text
    return recommands

def extract_values(data, key):
    return [dictionary[key] for dictionary in data]

def find_values(data, key, value):
    return [dictionary for dictionary in data if dictionary[key] == value]

def get_docs(url, raw=False):
    sess = requests.session()
    res = _get(sess, url, headers=SIMPLE_HEADERS)
    soup = BeautifulSoup(res.text, 'lxml')
    info = soup.select(DOC_SELECTOR)

    docs = []
    raw_docs = []
    for doc in info:
        if doc.find('td').getText() == '공지':
            continue
        doc_data = doc.find_all('td')
        doc_info = refine_doc_info(doc_data)
        raw_docs.append(doc_data)
        docs.append(doc_info)
    if raw:
        return raw_docs
    return docs

def get_pages_docs(gid, minor, start=1, end=1):
    pages = []
    for page in range(start, end+1):
        params = {'id':gid, 'page':str(page)}
        url = get_url(minor, params)
        docs = get_docs(url)

        pages.append(docs)
    return pages

def refine_pages_docs(pages):
    num_page = len(pages)
    if num_page == 1:
        return pages[0]

    temp_docs = []
    for idx, docs in enumerate(pages[::-1]):
        pre_index = (num_page - 2) - idx
        if pre_index < 0:
            temp_docs = docs + temp_docs
            break

        pre_docs = pages[pre_index]
        pre_keys = extract_values(pre_docs, 'no') #경계 게시글이 삭제될 경우 에러 발생 -> 시간으로 비교
        for jdx, doc in enumerate(docs):
            if doc['no'] in pre_keys:
                continue
            else:
                temp_docs = docs[jdx:] + temp_docs
                break
    return temp_docs

def get_docs_till_find_no(gid, minor, end_no):
    page = 1
    inf_docs = []
    while True:
        pages = get_pages_docs(gid, minor, start=page, end=page)
        inf_docs = inf_docs + pages
        docs = refine_pages_docs(inf_docs)

        nos = extract_values(docs, 'no')
        for idx, no in enumerate(nos):
            if int(end_no) > int(no):
                docs = docs[:idx - 1]
                return docs
        page += 1

def get_doc_info(gid, minor, doc_no):
    sess = requests.session()
    url = 'http://gall.dcinside.com/{}/board/view/?id={}&no={}'.format('mgallery' if is_miner else '', board, doc_no)
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.89 Safari/537.36"}
    res = _get(sess, url, headers=HEADERS)

    soup = BeautifulSoup(res.text, 'lxml')

    info = soup.select('#dgn_content_de > div.re_gall_top_1 > div.w_top_left > dl > dd')
    title = info[0].getText()
    user_info = info[1].select_one('span')
    user_id, user_name = user_info.get('user_id'), user_info.get('user_name')
    date = soup.select_one('#dgn_content_de > div.re_gall_top_1 > div.w_top_right > ul > li > b').getText()
    views = info[2].getText().strip()
    ip = soup.select_one('#dgn_content_de > div.re_gall_top_1 > div.w_top_right > ul > li.li_ip').getText().strip()
    votes = soup.select_one('#recommend_view_up').getText()

    return {
            "title": title, "user_name": user_name, "ip": ip, "date": date, 'user_id': user_id,
            "views": int(views), "recommands": int(votes), "doc_no": int(doc_no),
        }

###
#마갤과 정식갤 불러오는 방식
#마갤 - board/list 바로
#정식 - board/view 로 게시글 들어가서
#  => 공지 게시글(1번) 이용


###
def get_now_time():
    now = datetime.now()
    now_date = now.strftime('%H:%M:%S')
    return now_date

def tprint(text, **vals):
    txt = '[{}]'.format(get_now_time()) + str(text)
    print(txt, **vals)

def timout_func(func, seconds):
    @timeout_decorator.timeout(seconds)
    def timed_func(*args, **kwargs):
        func(*args, **kwargs)
    return timed_func
