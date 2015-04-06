#!/usr/bin/env python

### Original author: Dave Wolber via template of Hal Abelson and incorporating changes of Dean Sanvitale

### Customised by Shruti Rijhwani, March 2015

import webapp2

import logging
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.ext.db import Key
from django.utils import simplejson as json
from math import radians, cos, sin, asin, sqrt

import os
from google.appengine.ext.webapp import template
import urllib

import logging
import re


max_entries = 1000

class StoredData(db.Model):
  tag = db.StringProperty()
  value = db.TextProperty()
  date = db.DateTimeProperty(required=True, auto_now=True)

class BloodInfo(db.Model):
    email = db.StringProperty()
    location = db.GeoPtProperty()
    bloodType = db.StringProperty()
    enabled = db.BooleanProperty()

class DistanceBloodInfo(db.Model):
    email = db.StringProperty()
    distance = db.FloatProperty()



class StoreAValue(webapp2.RequestHandler):

  def store_a_value(self, tag, value):
    store(tag, value)

    result = ["STORED", tag, value]
    
    
    if self.request.get('fmt') == "html":
        WriteToWeb(self,tag,value)
    else:
        WriteToPhoneAfterStore(self,tag,value)
    

  def post(self):
    tag = self.request.get('tag')
    value = self.request.get('value')
    self.store_a_value(tag, value)

class DeleteEntry(webapp2.RequestHandler):

  def post(self):
    logging.debug('/deleteentry?%s\n|%s|' %
                  (self.request.query_string, self.request.body))
    entry_key_string = self.request.get('entry_key_string')
    key = db.Key(entry_key_string)
    tag = self.request.get('tag')
    if tag.startswith("http"):
      DeleteUrl(tag)
    db.run_in_transaction(dbSafeDelete,key)
    self.redirect('/')


class GetValueHandler(webapp2.RequestHandler):

    

    def get_value(self, tag):

        if '[' in tag:

            tagSplit = tag.replace("[","").replace("]","")
            tagList = tagSplit.split(',')
            tag1 = str(tagList[0]).strip()
            typeToFind = str(tagList[1]).replace("\"", " ").replace("  "," ").strip()
            lat = float(tagList[2])
            lon = float(tagList[3])
            if lat and typeToFind and lon:
                area = 0.5
                minLat = lat - area
                minLon = lon - area
                maxLat = lat + area
                maxLon = lon + area
                query = db.GqlQuery("SELECT * FROM BloodInfo WHERE location >= :1 AND location <= :2 AND enabled = True and bloodType = :3",db.GeoPt(lat=minLat, lon=minLon), db.GeoPt(lat=maxLat, lon=maxLon), typeToFind)

                distanceList = []
                value = ""

                for item in query:                
                    dist = haversine(lat, lon, item.location.lat, item.location.lon)
                    toAdd = DistanceBloodInfo(email = item.email, distance = dist)
                    distanceList.append(toAdd) 

                distanceList.sort(key=lambda x: x.distance, reverse=False)

                value = "["

                for item in distanceList:
                    result = db.GqlQuery("SELECT * FROM StoredData where tag = :1", item.email).get()
                    if result and result.tag != tag1:
                        value = value + "[" + result.tag + "," + result.value[1:-1] + "," + str(item.distance) +"],"

                if len(value) == 1:
                    value = "SEARCH_NOT_FOUND"
                else:
                	value = value[:-1] + "]"
            else: value = "SEARCH_NOT_FOUND"

        else:
            entry = db.GqlQuery("SELECT * FROM StoredData where tag = :1", tag).get()
            if entry:
               value = entry.value
            else: value = "USER_NOT_FOUND"

        if self.request.get('fmt') == "html":
            WriteToWeb(self,tag,value)
        else:
            WriteToPhone(self,tag,value)

    def post(self):
        tag = self.request.get('tag')
        self.get_value(tag)

    # there is a web ui for this as well, here is the get
    def get(self):
        # this did pump out the form
        template_values={}
        path = os.path.join(os.path.dirname(__file__),'index.html')
        self.response.out.write(template.render(path,template_values))


class MainPage(webapp2.RequestHandler):

  def get(self):
    entries = db.GqlQuery("SELECT * FROM StoredData ORDER BY date desc")
    template_values = {"entryList":entries}
    # render the page using the template engine
    path = os.path.join(os.path.dirname(__file__),'index.html')
    self.response.out.write(template.render(path,template_values))

#### Utilty procedures for generating the output

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    
    return c * 3958

def WriteToPhone(handler,tag,value):
 
    handler.response.headers['Content-Type'] = 'application/jsonrequest'
    json.dump(["VALUE", tag, value], handler.response.out)

def WriteToWeb(handler, tag,value):    
       
    entries = db.GqlQuery("SELECT * FROM StoredData ORDER BY date desc")

    template_values={"result":  value,"entryList":entries}
    path = os.path.join(os.path.dirname(__file__),'index.html')
    handler.response.out.write(template.render(path,template_values))

def WriteToPhoneAfterStore(handler,tag, value):
    handler.response.headers['Content-Type'] = 'application/jsonrequest'
    json.dump(["STORED", tag, value], handler.response.out)



### A utility that guards against attempts to delete a non-existent object
def dbSafeDelete(key):
  if db.get(key) :    db.delete(key)
  
def store(tag, value, bCheckIfTagExists=True):

    try:

        if bCheckIfTagExists:
            # There's a potential readers/writers error here :(
            entry = db.GqlQuery("SELECT * FROM StoredData where tag = :1", tag).get()
            if entry:
              entry.value = value
            else: entry = StoredData(tag = tag, value = value)
        else:
            entry = StoredData(tag = tag, value = value)
           


        newstr = value.replace("[","").replace("]","").replace("\"", " ").replace("  "," ")

        lis = newstr.split(',')



        if bCheckIfTagExists:
            # There's a potential readers/writers error here :(
            entry2 = db.GqlQuery("SELECT * FROM BloodInfo where email = :1", tag).get()
            if entry2:
              entry2.bloodType = str(lis[-4]).strip()
              entry2.location = db.GeoPt(float(lis[-3]), float(lis[-2]))
              entry2.enabled = True
            else: entry2 = BloodInfo(email = tag, bloodType = str(lis[-4]).strip(), location = db.GeoPt(float(lis[-3]), float(lis[-2])), enabled = True)

            if(int(lis[-1]) == 0):
                entry2.enabled = False
        else:
            entry2 = BloodInfo(email = tag, bloodType = str(lis[-4]).strip(), location = db.GeoPt(float(lis[-3]), float(lis[-2])), enabled = True)
            if(int(lis[-1]) == 0):
                entry2.enabled = False

        entry.put() 
        entry2.put()    
    except:
        return

    
def trimdb():
    ## If there are more than the max number of entries, flush the
    ## earliest entries.
    entries = db.GqlQuery("SELECT * FROM StoredData ORDER BY date")
    if (entries.count() > max_entries):
        for i in range(entries.count() - max_entries): 
            db.delete(entries.get())

from htmlentitydefs import name2codepoint 
def replace_entities(match):
    try:
        ent = match.group(1)
        if ent[0] == "#":
            if ent[1] == 'x' or ent[1] == 'X':
                return unichr(int(ent[2:], 16))
            else:
                return unichr(int(ent[1:], 10))
        return unichr(name2codepoint[ent])
    except:
        return match.group()

entity_re = re.compile(r'&(#?[A-Za-z0-9]+?);')

def html_unescape(data):
    return entity_re.sub(replace_entities, data)
    
def ProcessNode(node, sPath):
    entries = []
    if node.nodeType == minidom.Node.ELEMENT_NODE:
        value = ""
        for childNode in node.childNodes:
            if (childNode.nodeType == minidom.Node.TEXT_NODE) or (childNode.nodeType == minidom.Node.CDATA_SECTION_NODE):
                value += childNode.nodeValue

        value = value.strip()
        value = html_unescape(value)
        if len(value) > 0:
            entries.append(StoredData(tag = sPath, value = value))
        for attr in node.attributes.values():
            if len(attr.value.strip()) > 0:
                entries.append(StoredData(tag = sPath + ">" + attr.name, value = attr.value))
        
        childCounts = {}
        for childNode in node.childNodes:
            if childNode.nodeType == minidom.Node.ELEMENT_NODE:
                sTag = childNode.tagName
                try:
                    childCounts[sTag] = childCounts[sTag] + 1
                except:
                    childCounts[sTag] = 1
                if (childCounts[sTag] <= 5):
                    entries.extend(ProcessNode(childNode, sPath + ">" + sTag + str(childCounts[sTag])))
        return entries
        
def DeleteUrl(sUrl):
    entries = StoredData.all().filter('tag >=', sUrl).filter('tag <', sUrl + u'\ufffd')
    db.delete(entries[:500])
  

### Assign the classes to the URL's

app = webapp2.WSGIApplication ([('/', MainPage),
                           ('/getvalue', GetValueHandler),
               ('/storeavalue', StoreAValue),
                   ('/deleteentry', DeleteEntry)

                           ])



