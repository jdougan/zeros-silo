"""
    Silo -- a simple, general purpose file system for LSL via HTTP
        version 2006-07-09-beta
        by Zero Linden
    
        Copyright (c) 2006 Linden Lab
        Licensed under the "MIT" open source license.
    
    This file is only part of the whole distribution.
        test.py -- unit tests
"""

import os
import httplib
import sys
import time
import unittest
import urlparse

NeedsKey = False
#NeedsKey = True
    # if you change $firstPath in silo.php to be $keyPat
    # then change this to set NeedsKey to True

class Silo:
    
    def __init__(self, url):
        self.baseURL = url
        parts = urlparse.urlparse(url, 'http', False)
        (self.baseScheme, self.baseHost, self.basePath) = parts[0:3]
    
    def goodStatus(self, status):
        return 200 <= status and status < 300
        
    def ensureGoodStatus(self, status, content):
        if not self.goodStatus(status):
            raise "unexpected http error status %d: %s" % (status, str(content))
    
    def encode(self, body, encoding='utf-8'):
        headers = {}
        if body != None:
            body = unicode(body).encode(encoding)
            headers['Content-Type'] = 'text/plain;charset=' + encoding
        return (body, headers)
    
    def decode(self, rawContent, mimeType):
        if rawContent == None:
            return ''

        typeParts = mimeType.lower().split(';')
        if typeParts[0].strip().split('/')[0] != 'text':
            return ''

        charset = 'iso-8859-1'
        for param in typeParts[1:]:
            paramParts = param.lower().split('=', 1)
            if paramParts[0] == 'charset' and len(paramParts) == 2:
                charset = paramParts[1]

        return unicode(rawContent, charset)

    def rawConnect(self, verb, path, rawBody=None, headers={}):
        connection = httplib.HTTPConnection(self.baseHost)
        connection.request(verb, self.basePath + path, rawBody, headers)
        response = connection.getresponse()
        status = response.status
        rawContent = response.read()
        mimeType = response.getheader(
                        'Content-Type', 'application/octet-stream')
            # according to RFC 2616, section 7.2.1, we are allowed to guess
            # the mime type in the absence of the Content-Type header
            # however, LSL takes a stricter view and will not guess text
        return (status, rawContent, mimeType)

    def connect(self, verb, path, body=None, encoding='utf-8'):
        (rawBody, headers) = self.encode(body, encoding)
        (status, rawContent, mimeType) = \
             self.rawConnect(verb, path, rawBody, headers)
        content = self.decode(rawContent, mimeType)
        return (status, content)
    
    def get(self, path):
        (status, content) = self.connect("GET", path)
        self.ensureGoodStatus(status, content)
        return content
    
    def put(self, path, body, encoding='utf-8'):
        (status, content) = self.connect("PUT", path, body, encoding)
        self.ensureGoodStatus(status, content)
        return content
    
    def delete(self, path):
        (status, content) = self.connect("DELETE", path)
        self.ensureGoodStatus(status, content)
        return content
    
    def missing(self, path):
        (status, content) = self.connect("GET", path)
        if self.goodStatus(status):
            raise "unexpected (%d) status for %s: %s" \
                % (status, path, str(content))

silo = None

class Tests_A_Setup(unittest.TestCase):
    def test000_baseURL(self):
        self.failUnlessEqual(silo.baseScheme, 'http')
        self.failUnless(silo.baseHost)
        self.failUnless(silo.basePath)

        
class Tests_B_PathError(unittest.TestCase):
    def doPut(self, path, expectedOutcome):
        (status, content) = silo.connect("PUT", path, "data")
        if silo.goodStatus(status) != expectedOutcome:
            if expectedOutcome:
                expectedString = "good"
            else:
                expectedString = "bad"
            message = "expected %s status, got %d, processing path %s" % \
                (expectedString, status, path)
            self.fail(message)
    
    def doPutExpectGood(self, path):
        self.doPut(path, True)
    
    def doPutExpectBad(self, path):
        self.doPut(path, False)
        
    def test000_noPath(self):
        self.doPutExpectBad("")

    def test001_slashPath(self):
        self.doPutExpectBad("/")

    def test002_wordPath(self):
        self.doPut("/tuna-fish", not NeedsKey)

    def test003_badPath(self):
        self.doPutExpectBad("moo")

    def test004_dotPath(self):
        self.doPutExpectBad("/../../bin")

    def test005_hexPath(self):
        self.doPut("/E769FCEC3D1A4D538FC7BB3B0BBAFBEA", not NeedsKey)

    key = "/E769FCEC-3D1A-4D53-8FC7-BB3B0BBAFBEA"
    
    def test006_okayPath(self):
        self.doPutExpectGood(self.key + "/stuff")

    def test007_junkPath(self):
        self.doPutExpectBad(self.key + "/../foo")

    def test008_deepPath(self):
        self.doPutExpectBad(self.key + "/a/b/c/d/e/f/g/h/i/j/k")

    def test009_allowedCharacters(self):
        self.doPutExpectGood(self.key + "/0123456789")
        self.doPutExpectGood(self.key + "/ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        self.doPutExpectGood(self.key + "/abcdefghijklmnopqrstuvwxyz")
        
        allowedChars = "+-_"
        for c in allowedChars:
            self.doPutExpectGood(self.key + "/x" + c + "x")

        self.doPutExpectGood(self.key + "/%24x")
            # percent is only legal as an escape

    def test010_disallowedCharacters(self):
        disallowedPathChars = ".~:@!$&'()*,;=#?"
            # legal as part of a URI path, query or fragment (see RFC 3986)
        disallowedOtherChars = "\"<>[\\]^`{|}"
            # not legal in URI path, query or fragment
            # should include space and del, but cause some versions of Apache
            # heartburn if you do
            
        for c in (disallowedPathChars + disallowedOtherChars):
            self.doPutExpectBad(self.key + "/x" + c + "x")



class Tests_C_Basic(unittest.TestCase):
    key = "/66ba1038-23b1-49f6-889d-00aa436a7e57"
    
    def setUp(self):
        silo.delete(self.key)
        silo.delete(self.key + "/")
         
    def test000_clear(self):
        silo.missing(self.key)
        silo.missing(self.key + "/")
        
    def test001_basic(self):
        where = self.key + "/simple"
        silo.missing(where)
        silo.put(where, "lalala")
        r = silo.get(where)
        self.assertEquals(r, "lalala")
        silo.delete(where)
        silo.missing(where)
        
    def test002_nestedData(self):
        above = self.key + "/nested/above"
        below = above + "/below"
        silo.put(above, "alpha");
        silo.put(below, "beta");
        self.assertEquals(silo.get(above), "alpha")
        self.assertEquals(silo.get(below), "beta")
        
    def test003_dirListing(self):
        silo.put(self.key + "/one", "uno")
        silo.put(self.key + "/two", "due")
        silo.put(self.key + "/three", "tre")
        r = silo.get(self.key + "/")
        self.assertEquals(r, "one\nthree\ntwo\n")
    
    def ensureWriteToFirstReadsFromSecond(self, keyA, keyB, delDir = False):
        silo.put(keyA, "insensitive")
        self.assertEqual(silo.get(keyB), "insensitive")
        
        delKey = keyB
        if delDir:
            delKey = keyB[:keyB.rfind('/')+1]
        silo.delete(delKey)
        silo.missing(keyA)
    
    def ensureKeysAreEquivalent(self, keyA, keyB, delDir = False):
        self.ensureWriteToFirstReadsFromSecond(keyA, keyB, delDir)
        self.ensureWriteToFirstReadsFromSecond(keyB, keyA, delDir)

    def test004_caseSensitivity(self):
        self.ensureKeysAreEquivalent(
            self.key.upper() + "/d",
            self.key.lower() + "/d",
            True)
            
        self.ensureKeysAreEquivalent(
            self.key.upper() + "/f",
            self.key.lower() + "/f",
            False)
    
    def test005_putStatus(self):
        k = self.key + "/new-node"
        (status, content) = silo.connect("PUT", k, "first time")
        self.assertEquals(status, 201)
        (status, content) = silo.connect("PUT", k, "second time")
        self.assertEquals(status, 200)
    
class Tests_D_RoundTrip(unittest.TestCase):
    key = "/fa4b13c9-ed3c-462a-be6a-011c1bc464a9"
    
    def setUp(self):
        silo.delete(self.key)
        silo.delete(self.key + "/")
         
    def test000_clear(self):
        silo.missing(self.key)
        silo.missing(self.key + "/")
    
    def roundTrip(self, value, encoding="utf-8"):
        silo.put(self.key, value, encoding)
        self.assertEquals(silo.get(self.key), value)
    
    def test001_simple(self):
        self.roundTrip("")
        self.roundTrip(" ")
        self.roundTrip("a")
        self.roundTrip("&<=>")

    def test002_asciiPrinting(self):
        self.roundTrip(' !"#$%&\'()*+,-./')
        self.roundTrip('0123456789:;<=>?')
        self.roundTrip('@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_')
        self.roundTrip('`abcdefghijklmnopqrstuvwxyz{|}~')

    def test003_encodingASCII(self):
        self.roundTrip("hello there", 'us-ascii')

    def test004_encodingISOLatin1(self):
        self.roundTrip(u'\u00C5ngstr\u00F6m', 'iso-8859-1')

    def test005_encodingUTF16(self):
        self.roundTrip(u'\u00C5ngstr\u00F6m \u03b2 \u2222', 'utf-16')

    def test006_encodingUTF16LE(self):
        self.roundTrip(u'\u00C5ngstr\u00F6m \u03b2 \u2222', 'utf-16le')

    def test007_encodingUTF16BE(self):
        self.roundTrip(u'\u00C5ngstr\u00F6m \u03b2 \u2222', 'utf-16be')


class Tests_Z_Timing(unittest.TestCase):
    key = '/55f62fac-b5ee-467a-9e3e-0e8cad0cd0de'
    
    def genKey(self):
        import uuid
        return "/" + str(uuid.uuid4())
    
    def readWriteKeys(self, keys):
        import random
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789-+.:"
        data = ''.join([ random.choice(alphabet) for i in range(100)])
        
        for k in keys:
            silo.put(k, data)
            self.assertEquals(silo.get(k), data)
    
    def deleteKeys(self, keys):
        for k in keys:
            silo.delete(k)
            
    def timingRuns(self, keyCount):
        (status, content) = silo.connect("GET", self.key)
        self.failIf(silo.goodStatus(status),
            "the silo's data tree isn't clear; try 'rm -rf data/*'")
        silo.put(self.key, "marker")
        
        keys = [ self.genKey() for i in range(keyCount)]
        for i in range(3):
            self.readWriteKeys(keys)
        self.deleteKeys(keys)

    def time10(self):
        self.timingRuns(10)
    
    def time100(self):
        self.timingRuns(100)
    
    def time1k(self):
        self.timingRuns(1000)
    
    def time10k(self):
        self.timingRuns(10000)
        
if __name__ == '__main__':
    silo = Silo(sys.argv[1])
    del sys.argv[1]
    unittest.main()

