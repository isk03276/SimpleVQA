#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
voice_cmd_vel.py is a simple demo of speech recognition.
  You can control a mobile base using commands found
  in the corpus file.
"""

import roslib; roslib.load_manifest('pocketsphinx')
import rospy
import math
from rospy import sleep

from std_msgs.msg import String

import os, sys
import re

from sound_play.msg import SoundRequest 
from sound_play.libsoundplay import SoundClient
sys.path.append('/home/ailab/catkin_ws/install/lib/qsr_lib')
from ob_subscriber import *

_pattern_rule = ""



class vqa:
    def __init__(self):
        self.msg = ""
	self.switch = False
	self.m = None
	self.count=0
	self.soundhandle = SoundClient()
        # publish to cmd_vel, subscribe to speech output
        self.pub_ = rospy.Publisher('vqa', String, queue_size =1 )
        self.sub = rospy.Subscriber('recognizer/output', String, self.callback)

        r = rospy.Rate(10.0)
        while not rospy.is_shutdown():
            r.sleep()
        
    def callback(self, msg):
	self.sub.unregister()
	self.soundhandle.stopAll()
	self.msg = msg
	self.msg = str(msg)[6:]
	self.pub_.publish(self.msg)
	if self.switch == True :
		if self.msg == 'robot stop':
			Change_Topic(0)
			Clear_XY()
			self.soundhandle.say('robot stopped')
			self.pub_.publish('***robot stopped')
			self.switch = False
			self.sub = rospy.Subscriber('recognizer/output', String, self.callback)
		elif self.msg == 'finish robot':
			self.soundhandle.say('robot is finished')
			sys.exit()

		else:
			self.send(self.msg)
	else :
		if self.msg.count('robot start') == 1:
			self.soundhandle.say("please wait for seconds")
			self.pub_.publish("***please wait for seconds")
			Change_Topic(1)
			rospy.sleep(5)
			
			chk_str = Chk_Obj()
			if chk_str[0] == "":
				Change_Topic(0)
				self.pub_.publish('***robot is started')
				self.soundhandle.say("i'm ready")	
				self.switch = True
			else:
				
				if chk_str[1] == 1:
					self.pub_.publish('***%s is not detected'%chk_str[0])
					self.soundhandle.say("%s is not detected, robot stopped"%chk_str[0])
				else:
					self.pub_.publish('***%s are not detected'%chk_str[0])
					self.soundhandle.say("%s are not detected, robot stopped"%chk_str[0])
				self.pub_.publish('***robot stopped')
				Change_Topic(0)
				Clear_XY()
				self.switch = False
		self.sub = rospy.Subscriber('recognizer/output', String, self.callback)
    def send(self, msg):	#send_msg
	global _pattern_rule
	self.m = _pattern_rule.match(msg.lower())
	if self.m is not None:
		self.pub_.publish("***pattern success")
		self.create_msg(msg)
		self.count=0
	elif self.count == 5 :
		self.soundhandle.stopAll()
		self.soundhandle.say('check the manual please,      robot stopped')
		self.pub_.publish('***check the manual, please')
		self.count =0
		self.switch = False
	        self.pub_.publish('***robot stopped')
		Change_Topic(0)
		Clear_XY()
		self.sub = rospy.Subscriber('recognizer/output', String, self.callback)
	else :
		self.soundhandle.say('speak again please')
		self.count += 1		
		self.sub = rospy.Subscriber('recognizer/output', String, self.callback)
    def create_msg(self, msg):
	self.soundhandle.stopAll()
	base_object=self.m.group(3)
	direction=self.m.group(2)
	object_f = Req_Obj(base_object, direction)
	#object_f = str(object_f)[15:]
	if object_f == 'NONE':
		self.soundhandle.say('there is nothing')
	elif object_f.count(','):
		object_f = object_f.replace(",", " and ")
		self.soundhandle.say('They are ' + object_f)
	else :
		self.soundhandle.say('It is a ' + object_f)
	self.sub = rospy.Subscriber('recognizer/output', String, self.callback)
####################
    
if __name__=="__main__":
    Add_Three_Object()
    Init_Qsr()
    rospy.init_node('vqa')
    _pattern_rule = re.compile( '(what|right).*(right|left|under|upside).*(book|calendar|box).*')
    vqa()

