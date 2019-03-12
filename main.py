# -*- encoding:utf-8 -*-
import ConfigParser
import codecs
import random
import threading
import time
import requests
import threadpool
import subprocess
import logging
import sys
import json
import traceback

requests.packages.urllib3.disable_warnings()
task_pool = threadpool.ThreadPool(20)

cfg = ConfigParser.ConfigParser()
cfg.readfp(codecs.open('config.ini', 'r', 'utf-8-sig'))

BASE_URL = cfg.get('server', 'base_url')

USER_NAME = cfg.get('server', 'p_usr')
PASS_WORD = cfg.get('server', 'p_pwd')

ADSL_NAME = cfg.get('adsl', 'name')
ADSL_ACCOUNT = cfg.get('adsl', 'account')
ADSL_PASSWORD = cfg.get('adsl', 'password')

VPS_ENABLE = cfg.get('vps', 'enable')
VPS_URL = cfg.get('vps', 'url')
VPS_QU = cfg.get('vps', 'qu')


def check_adsl():
    result = subprocess.check_output(u'Rasdial')
    # '\xd2\xd1\xc1\xac\xbd\xd3' 表示 '已连接'
    if result.find('\xd2\xd1\xc1\xac\xbd\xd3') >= 0:
        return True
    else:
        return False
    # return True


def change_city(province_name, city_name):
    # type: (str, str) -> bool
    if int(VPS_ENABLE) == 0:
        return False
    print(u'尝试切换城市')

    # 处理省市名
    if province_name.endswith('市'):
        province_name = province_name.replace('市', '')
    elif province_name.endswith('省'):
        province_name = province_name.replace('省', '')
    else:
        print(u'收到的provinceName非“省”或“市”结尾.')

    if city_name.endswith('市'):
        city_name = city_name.replace('市', '')
    else:
        print(u'收到的cityName非“市”结尾.')

    # 尝试登录
    print(u'尝试登录')
    params = {'username': ADSL_ACCOUNT, 'password': ADSL_PASSWORD, 'arg': 'login_info', 'qu': VPS_QU}
    res = None
    try:
        res = requests.get(VPS_URL, params, timeout=10)
        json_data = res.json()
        if json_data.has_key('response') and len(json_data['response']) > 0 and int(json_data['response']['errorCode']) < 0:
            print(u'VPS账号登录失败:' + json_data['response']['msg'])
            return False
        params['groupid'] = json_data['responseBody']['groupid']
    except Exception as e:
        if res is not None:
            print(res.text)
        print(u'VPS站点无法连接\nException:\n' + str(e))
        return False
    print(u'登陆成功')

    # 获取VPS列表
    params['arg'] = 'area'
    try:
        res = requests.get(VPS_URL, params, timeout=10)
        json_data = res.json()
        if json_data['code'] != u'1':
            print(res.text)
            print(u'VPS站点服务器列表获取失败.')
            return False
        cities = [city for city in json_data['list']
                  if city_name in city['areaname'].encode('utf8')
                  and city['status'] == u'1']
    except Exception as e:
        if res is not None:
            print(res.text)
        print(u'VPS站点无法连接\nException:\n' + str(e))
        return False

    task_pool.wait()
    params['arg'] = 'update_area'
    if len(cities) != 0:
        # 换地区
        params.pop('groupid')
        random.shuffle(cities)
        for city in cities:
            try:
                params['srvid'] = city['srvid']
                res = requests.get(VPS_URL, params, timeout=10)
                json_data = res.json()
                if json_data.has_key('response') and len(json_data['response']) > 0 and int(json_data['response']['errorCode']) < 0:
                    if check_adsl():
                        return True
                    continue
                    print(u'VPS站点切换失败:' + json_data['response']['msg'])
                if json_data['result'] != u'ok':
                    print(res.text)
                    if check_adsl():
                        return True
                    continue
                    print(u'切换到srvid为' + city['srvid'] + u'的VPS站点失败.')
                print(u'成功切换到' + json_data['responseBody']['areaname'])
                return True
            except Exception as e:
                if check_adsl():
                    return True
                print(u'切换到srvid为' + city['srvid'] + u'的VPS站点失败.\nException:\n' + str(e))
                continue

    print(u'找不到同市的VPS站点')
    cities = [city for city in json_data['list']
              if province_name in city['areaname'].encode('utf8')
              and city['status'] == u'1']
    random.shuffle(cities)
    for city in cities:
        try:
            params['srvid'] = city['srvid']
            res = requests.get(VPS_URL, params, timeout=10)
            json_data = res.json()
            if json_data.has_key('response') and len(json_data['response']) > 0 and int(json_data['response']['errorCode']) < 0:
                print(u'VPS站点切换失败:' + json_data['response']['msg'])
                continue
            if json_data['result'] != u'ok':
                print(res.text)
                print(u'切换到srvid为' + city['srvid'] + u'的VPS站点失败.')
                continue
            print(u'成功切换到' + json_data['responseBody']['areaname'])
            return True
        except Exception as e:
            print(u'切换到srvid为' + city['srvid'] + u'的VPS站点失败.\nException:\n' + str(e))
            continue

    print(u'找不到可用的' + province_name + city_name + u'的VPS站点')
    return False


def kill(p):
    try:
        p.kill()
    except OSError:
        pass


def redial():
    """
    重播号
    """
    print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(
        time.time())) + u'] 重播号...')
    try:
        result = subprocess.check_output(
            u'Rasdial {0} /d'.format(ADSL_NAME).encode(
                sys.getfilesystemencoding()))
        if result.find('756') >= 0:
            exit('756')
        p = subprocess.Popen(
            u'Rasdial {0} {1} {2}'.format(ADSL_NAME, ADSL_ACCOUNT,
                                          ADSL_PASSWORD).encode(
                sys.getfilesystemencoding()),
            shell=True)
        t = threading.Timer(20, kill, [p])
        t.start()
        p.wait()
        t.cancel()
        if not check_adsl():
            exit('756')
    except:
        logging.exception(traceback.format_exc())
        time.sleep(20)
        if check_adsl() is True:
            return
        redial()


def get_task(username, password):
    """
    获取任务
    """

    params = {'UserName': username, 'Password': password}
    headers = {'Accept': 'application/json'}
    url = str(BASE_URL + '/api/Task')
    json_data = None
    for x in xrange(1, 3):
        print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(time.time())) +
              u'] 正在获取任务....')
        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            # res.encoding = res.apparent_encoding
            # print(res.text.encode(res.encoding))
            print(res.text)
            if res.status_code == 200:
                json_data = res.json()
                break
        except Exception as e:
            print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.localtime(time.time())) +
                  u'] 获取任务错误.\nException:\n' + str(e))
            continue
    if json_data is None:
        return None
    if json_data['code'] != 200:
        logging.exception(json_data['message'])
    return json_data['data']


def update_task(taskobj):
    """
    更新任务状态
    """
    params = {'taskId': taskobj.pop('taskGuid')}
    body = json.JSONEncoder().encode(taskobj)
    try:
        headers = {'Content-Type': 'application/json'}
        url = str(BASE_URL + '/api/task/' + params['taskId'])
        for x in xrange(1, 3):
            req = requests.post(url, data=body, headers=headers, timeout=20)
            if req.status_code == 200:
                break
        print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 任务更新 > ' + params[
            'taskId'] + ' > ' + str(req.status_code))
        # if req.status_code == 201:
        #     print(u'任务 {0} 更新成功'.format(task_id))
        # else:
        #     print(u'任务 {0} 更新失败'.format(task_id))
    except Exception as e:
        print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 任务更新失败 > ' + params[
            'taskId'] + u' > ' + str(e))
        # update_task(task_id, status, res)


def do_task(data):
    """
    处理任务
    """

    print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 执行任务 > ' + data['taskGuid'])
    d = {}
    upload = []
    try:
        for on_task in data["requestList"]:
            try:
                # print(on_task)
                method = on_task['method']
                headers = {}

                s_headers = on_task['header']
                if s_headers == '':
                    v_headers = []
                else:
                    v_headers = s_headers.split('\r\n')

                for h in v_headers:
                    key_val = h.split(':')
                    if len(key_val) != 2:
                        print(u'> header格式有误，请服务端修正. \r\n')
                        return
                    headers[key_val[0].strip()] = key_val[1].strip()

                url = on_task['url']
                # print(u'> ' + url)
                res = None
                for x in xrange(1, 3):
                    try:
                        if method == 'POST' or method == 'post':
                            res = requests.post(url, headers=headers,
                                                data=on_task['body'], verify=False, timeout=15)
                        else:
                            res = requests.get(url, headers=headers, timeout=15)
                        if res.status_code / 100 == 2:
                            break
                    except Exception as e:
                        print(u'> 执行任务出错，重试. \r\n' + str(e))
                if res is None:
                    print(u'> 执行任务出错，放弃.\r\n')
                    return
                print(u'> ' + str(res.status_code))
                task = {'id': on_task['id'], 'code': res.status_code, 'header': res.headers.__str__(), 'body': res.text}
                upload += [task]

                # update_task(on_task['id'], status, res)
            except Exception as e:
                print(u'> 执行任务出错，放弃.\r\n' + str(e))
                return
    except Exception as e:
        print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 解析任务出错，可能是空任务.' + str(e))

    try:
        d['taskGuid'] = data['taskGuid']
        d['userName'] = USER_NAME
        d['password'] = PASS_WORD
        d['responseList'] = upload
        update_task(d)
    except Exception as e:
        print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 更新任务出错，' + str(e))


def main():
    print(ADSL_NAME)
    print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(
        time.time())) + u'] 程序开始运行.')

    cur_task_index = 0
    for x in xrange(0, 10):
        try:
            print(u'开始执行...')
            print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.localtime(time.time())) +
                  u'] 检查拨号状态')
            if check_adsl() is False:
                redial()

            task = get_task(USER_NAME, PASS_WORD)
            if task is None:
                print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 获取任务失败，重新拨号....')
                redial()
                continue

            if cur_task_index >= 20:
                print('达到20个线程，等待线程结束')
                task_pool.wait()
                cur_task_index = 0

            if task['changeCity'] is True:
                # 需要更换城市，先等待线程池完毕
                print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 等待线程池返回....')
                task_pool.wait()
                print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 线程池结束....')

                if change_city(task['provinceName'].encode('utf8'), task['cityName'].encode('utf8')):
                    redial()
                    cur_task_index = 0
                # 重新获取任务
                continue

            if task['changeIp'] is True:
                # 需要更换IP，先等待线程池完毕
                print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 等待线程池返回....')
                task_pool.wait()
                print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 线程池结束....')
                redial()
                cur_task_index = 0

                # 重新获取任务
                continue

            if task['requestList'] is None or task['requestList'].__len__() == 0:
                print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 当前无任务....')
                # 重新获取任务
                print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 等待1秒....')
                time.sleep(1)
                continue

            cur_task_index = cur_task_index + 1
            print(u'正在派发任务' + str(cur_task_index))
            task_list = [task]
            # do_task(task)
            req = threadpool.makeRequests(do_task, task_list)
            for r in req:
                task_pool.putRequest(r)
            time.sleep(1)
        except Exception as e:
            print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] Error:' + str(e))
            print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 等待线程池返回....')
            task_pool.wait()
            print(u'[' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + u'] 线程池结束....')
            redial()
            cur_task_index = 0


if __name__ == '__main__':
    main()
    task_pool.wait()
