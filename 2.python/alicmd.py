#!/usr/bin/env python
#coding=utf-8

DOCUMENTATION = '''
---
commmand line tool for AliYun OSS

author: Mick Duan
notes: []
requirements: [ CNC's AliYun OSS Python JDK, Python 2.6, 2.7 ]
'''

import os
import sys
import datetime
import re
import ConfigParser
import time
import signal
from optparse import OptionParser
reload(sys)
sys.setdefaultencoding("utf-8")
sys.path.append("/opt/ncscripts/oss")
from oss.oss_api import *
from oss.oss_util import *
from oss.oss_xml_handler import *
from base64 import b64encode,b64decode
import hashlib


#####constant setting####
DEFAULT_BUCKET="chinanetcloud"
OSS_PREFIX = 'oss://'
CONFIGFILE="/etc/.alioss.conf"
DEFAUL_HOST = "oss.aliyuncs.com"
CONFIGSECTION = 'oss'
SECRET='}0;&KlQph(@areU3Kf{Q8*7Pp.+L.SgFDk,[~$co[q)Tb/_nMVSw2(D1b;ow%Mq'

######default setting###########
ID = ""
KEY = ""
PUT_OK = 0
GET_OK = 0
DELETE_OK = 0
COPY_OK = 0
SEND_BUF_SIZE = 8192
RECV_BUF_SIZE = 1024*1024*10
MAX_OBJECT_SIZE = 5*1024*1024*1024
MAX_RETRY_TIMES = 3
IS_DEBUG = False

#####Version#####
version = '1.0.1'

######Time setting###########
T=datetime.datetime.now()
YEAR=T.strftime('%Y')
MOUTH=T.strftime('%m')
DAY=T.strftime('%d')
DATE_TIME=time.strftime('%Y-%m-%d-%H:%M',time.localtime(time.time()))


#####check Env functions###
def check_args(argv, args=None):
    if not args:
        args = []
    if len(args) < argv:
        print "%s miss parameters" % args[0]
        sys.exit(1)

def check_localfile(localfile):
    if not os.path.isfile(localfile):
        print "%s is not existed!" % localfile
        sys.exit(1)


def encode(unicodeString,key):
    """
    for safe: encode password & store it into config filef
    """
    strorg=unicodeString.encode('utf-8')
    strlength=len(strorg)
    baselength=len(key)
    hh=[]
    for i in range(strlength):
        hh.append(chr((ord(strorg[i])+ord(key[i % baselength]))%256))
    return b64encode(''.join(hh))

def alicmd_config():
    print "[INFO]: Start to config AliYun Open Storage Service."
    orig_id=raw_input("Please input your ACCESS_ID: ")
    orig_key=raw_input("Please input your ACCESS_KEY: ")
    bucket=raw_input("Please input your bucket: ")
    cnc_servername=raw_input("Plase input CNC server name: ")

    #for safe: encode password & store it into config file

    try:
        ID=encode(orig_id,SECRET)
        KEY=encode(orig_key,SECRET)
    except:
        print "[ERROR]: Failed to encrypt the key/ID"
        sys.exit(1)

    config = ConfigParser.RawConfigParser()
    config.add_section("oss")
    config.add_section("options")

    config.set("oss", 'access_key', KEY)
    config.set("oss", 'access_id', ID)
    config.set("oss", 'host', DEFAUL_HOST)
    config.set("oss", 'cnc_servername', cnc_servername)
    config.set("oss", 'bucket', bucket)
    config.set("options", 'retry_times', 3)
    config.set("options", 'thread_num', 10)
    config.set("options", 'max_part_num', 1000)
    config.set("options", 'timeout', 86400)
    config.set("options", 'multi-upload', "off")
    config.set("options", 'send_buf_size', 8192)
    cfgfile = open(CONFIGFILE, 'w+')
    config.write(cfgfile)
    print "Your configuration is saved into %s ." % CONFIGFILE
    cfgfile.close()


class OssCnf(object):
    """
    For more safe setting:
    encode: store passwd into cnf file
    decode: read passwd from cnf file

    retrun: id, key, host, bucket, cnc_
    """
    def __init__(self,cnffile):
        self.osscnf = {}
        self.status = True
        try:
            config = self.ReadConfig(cnffile)
            self.osscnf['id'] = str(self.Decode(config.get("oss", "ACCESS_ID"),SECRET))
            self.osscnf['key'] = str(self.Decode(config.get("oss", "ACCESS_KEY"),SECRET))
            self.osscnf['host'] = config.get("oss", "HOST")
            self.osscnf['bucket'] = config.get("oss", "bucket")
            self.osscnf['cnc_servername'] = config.get("oss", "cnc_servername")
            self.osscnf['retry_times'] = config.get("options", "retry_times")
            self.osscnf['thread_num'] = config.get("options", "thread_num")
            self.osscnf['max_part_num'] = config.get("options", "max_part_num")
            self.osscnf['timeout'] = config.get("options", "timeout")
            self.osscnf['multi-upload'] = config.get("options", "multi-upload")
            self.osscnf['send_buf_size'] = config.get("options", "send_buf_size")
        except Exception,e:
            print '*** Caught exception - Configuration File Error: %s :\n%s: %s\n' % (cnffile ,e.__class__, e)
            self.status = False

    def ReadConfig(self,cnfconfig):
        """
        read configurtion file, and return config
        """
        config = ConfigParser.ConfigParser()
        config.readfp(open(cnfconfig))
        return config

    def Decode(self,orig,key):
        """
        for safe: read config file & decode password
        """
        strorg = b64decode(orig.encode('utf-8'))
        strlength=len(strorg)
        keylength=len(key)
        hh=[]
        for i in range(strlength):
            hh.append((ord(strorg[i])-ord(key[i%keylength]))%256)
        return ''.join(chr(i) for i in hh).decode('utf-8')

class OssApi(object):
    def __init__(self, cnfconfig):
        self.cnfconfig = cnfconfig
        self.oss = self.Connect(cnfconfig['host'], cnfconfig['id'], cnfconfig['key'])

    def Connect(self, OSS_HOST, ID, KEY):
        SEND_BUF_SIZE = (int)(self.cnfconfig['send_buf_size'])
        oss = OssAPI(OSS_HOST, ID, KEY)
        oss.show_bar = True
        oss.set_send_buf_size(SEND_BUF_SIZE)
        oss.set_recv_buf_size(RECV_BUF_SIZE)
        return oss

    def GetStatus(self):
        return self.oss.get_service()

    def MultiUpload(self, localfile):
        """
        Upload localfile to OSS
        """
        upload_id = ""
        headers=None
        params=None
        thread_num = (int)(self.cnfconfig['thread_num'])
        max_part_num = (int)(self.cnfconfig['max_part_num'])
        retry_times = (int)(self.cnfconfig['retry_times'])
        self.bucket = self.cnfconfig['bucket']
        self.object = self.parse_object(self.cnfconfig['cnc_servername'], DATE_TIME, localfile)

        check_localfile(localfile)
        #user specified objectname oss://bucket/[path]/object

        self.oss.set_retry_times(retry_times)

        timeout = (int)(self.cnfconfig['timeout'])

        try:
            signal.alarm(timeout)
        except:
            pass
        upload_done = False
        upload_nu = 0
        while not upload_done:
            try:
                res = self.oss.multi_upload_file(self.bucket, self.object,  localfile, upload_id, thread_num, max_part_num, headers, params)
                upload_done = True
            except:
                if upload_nu < 5:
                    break
                else:
                    upload_nu += 1

        try:
            signal.alarm(0) # Disable the signal
        except:
            pass

        try:
            if res.status == 200:
                filesize = (int)(self.GetSize())
                if os.path.getsize(localfile) == filesize:
                    print self.GetMD5(localfile)
                else:
                    print "[ERROR]: File size difference between from OSS."
                    sys.exit(1)
            else:
                body = res.read()
                print "[ERROR]: Failed!\n%s" % body
                sys.exit(1)
        except:
            print "[ERROR]: no upload response - Upload Failed!"
            sys.exit(1)
        return res


    def Upload(self, localfile):
        """
        Upload a file without mutlt parts, better use this way: because it will return md5 from oss.
        """
        check_localfile(localfile)
        if os.path.getsize(localfile) > MAX_OBJECT_SIZE:
            print "locafile:%s is bigger than %s, it is not support by put, please use multiupload instead." % (localfile, MAX_OBJECT_SIZE)
            sys.exit(1)
        #user specified objectname oss://bucket/[path]/object
        self.bucket = self.cnfconfig['bucket']
        self.object = self.parse_object(self.cnfconfig['cnc_servername'], DATE_TIME, localfile)

        content_type = ""
        headers = {}

        timeout = (int)(self.cnfconfig['timeout'])

        try:
            signal.alarm(timeout)
        except:
            pass

        upload_done = False
        upload_nu = 0
        while not upload_done:
            try:
                res = self.oss.put_object_from_file(self.bucket, self.object, localfile, content_type, headers)
                upload_done = True
            except:
                if upload_nu < 5:
                    break
                else:
                    upload_nu += 1
        try:
            signal.alarm(0) # Disable the signal
        except:
            pass

        try:
            if res.status == 200:
                md5 = res.getheader("etag")
                print md5.strip('"').lower()
            else:
                body = res.read()
                print "[ERROR]: Failed!\n%s" % body
                sys.exit(1)
        except:
            print "[ERROR]: no upload response -  Upload Failed! "
            sys.exit(1)

        return res


    def parse_object(self, cnc_servername, time, filepath):
        file = os.path.basename(filepath)
        object = cnc_servername + "/" + time + "/" + file
        return object

    def GetSize(self):
        res = self.oss.get_object_info(self.bucket, self.object)
        if res.status == 200:
            for line in res.read().splitlines():
                m = re.search(r"\s<Size>(\d+)",line)
                if m:
                    return m.groups()[0]

    def GetMD5(self, filename):
        m = hashlib.md5()
        a_file = open(filename, 'rb')    #use binary read this file.
        m.update(a_file.read())
        a_file.close()
        return m.hexdigest()


def alicmd_show():
    """
    verify your Aliyun OSS configuration
    """
    cnf = OssCnf(CONFIGFILE)
    cnfdict = cnf.osscnf
    oss = OssApi(cnfdict)
    res = oss.GetStatus()
    if res.status == 200:
        http_body = res.read()
        bucket_list = GetServiceXml(http_body)
        print "Successful connect OSS:"
        for bucket in bucket_list.list():
            result=re.sub(r'(\(|\)|u?\'|,)','',str(bucket))
            print result
    else:
        body = res.read()
        print "[ERROR]: Failed!\n%s" % body
        sys.exit(1)

# MAIN
def main(options):
    if not options.config:
        alicmd_config()
        sys.exit(0)

    if not options.show:
        alicmd_show()
        sys.exit(0)

    cnf = OssCnf(CONFIGFILE)
    if not cnf.status:
        print "ERROR: Can't load config file: %s" % CONFIGFILE
        sys.exit(0)

    cnfdict = cnf.osscnf

    if options.filename:
        oss = OssApi(cnfdict)
        if cnfdict['multi-upload'] == "on":
            oss.MultiUpload(options.filename)
        else:
            oss.Upload(options.filename)
        sys.exit(0)

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-c", "--config",action="store_false", default=True ,help="config Aliyun OSS. You need to get ACCESS_KEY and ACCESS_ID first, file: %s " % CONFIGFILE)
    parser.add_option("-u", "--upload", dest="filename", help="upload a file to your bucket ")
    parser.add_option("-s", "--show", action="store_false", default=True, help="verify your Aliyun OSS configuration, will show all your buckets")
    (options, args) = parser.parse_args()
    main(options)
