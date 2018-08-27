#!/usr/bin/env python

import roslib; roslib.load_manifest('pocketsphinx')
import rospy

import pygtk
pygtk.require('2.0')
import gtk

import gobject
import pygst
pygst.require('0.10')
gobject.threads_init()
import gst

from std_msgs.msg import String
from std_srvs.srv import *
from pocketsphinx.srv import stt, tc

import os, sys
import re
import commands

from sound_play.msg import SoundRequest 
from sound_play.libsoundplay import SoundClient 

_pattern_rule = ""
m = None
switch = False
class recognizer(object):
    """ GStreamer based speech recognizer. """
    switch = True   ############# start_service or stop_service
    lines = []
    soundhandle = SoundClient()
    global _pattern_rule
    def __init__(self):
        # Start node
        rospy.init_node("recognizer")
	self.count = 0

        self._device_name_param = "~mic_name"  # Find the name of your microphone by typing pacmd list-sources in the terminal
        self._lm_param = "~lm"
        self._dic_param = "~dict"

        # Configure mics with gstreamer launch config
        if rospy.has_param(self._device_name_param):
            self.device_name = rospy.get_param(self._device_name_param)
            self.device_index = self.pulse_index_from_name(self.device_name)
            self.launch_config = "pulsesrc device=" + str(self.device_index)
            rospy.loginfo("Using: pulsesrc device=%s name=%s", self.device_index, self.device_name)
        elif rospy.has_param('~source'):
            # common sources: 'alsasrc'
            self.launch_config = rospy.get_param('~source')
        else:
            self.launch_config = 'gconfaudiosrc'

        rospy.loginfo("Launch config: %s", self.launch_config)

        self.launch_config += " ! audioconvert ! audioresample " \
                            + '! vader name=vad auto-threshold=true ' \
                            + '! pocketsphinx name=asr ! fakesink'

        # Configure ROS settings
        self.started = False
        rospy.on_shutdown(self.shutdown)
        self.pub = rospy.Publisher('~output', String)
        rospy.Service("~start", Empty, self.start)
        rospy.Service("~stop", Empty, self.stop)

        if rospy.has_param(self._lm_param) and rospy.has_param(self._dic_param):
            self.start_recognizer()
        else:
            rospy.logwarn("lm and dic parameters need to be set to start recognizer.")
	     
    def start_recognizer(self):
        rospy.loginfo("Starting recognizer... ")

        self.pipeline = gst.parse_launch(self.launch_config)
        self.asr = self.pipeline.get_by_name('asr')
        self.asr.connect('partial_result', self.asr_partial_result)
        self.asr.connect('result', self.asr_result)
        self.asr.set_property('configured', True)
        self.asr.set_property('dsratio', 1)

        # Configure language model
        if rospy.has_param(self._lm_param):
            lm = rospy.get_param(self._lm_param)
        else:
            rospy.logerr('Recognizer not started. Please specify a language model file.')
            return

        if rospy.has_param(self._dic_param):
            dic = rospy.get_param(self._dic_param)
        else:
            rospy.logerr('Recognizer not started. Please specify a dictionary.')
            return

        self.asr.set_property('lm', lm)
        self.asr.set_property('dict', dic)

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus_id = self.bus.connect('message::application', self.application_message)
        self.pipeline.set_state(gst.STATE_PLAYING)
        self.started = True

    def pulse_index_from_name(self, name):
        output = commands.getstatusoutput("pacmd list-sources | grep -B 1 'name: <" + name + ">' | grep -o -P '(?<=index: )[0-9]*'")

        if len(output) == 2:
            return output[1]
        else:
            raise Exception("Error. pulse index doesn't exist for name: " + name)

    def stop_recognizer(self):
        if self.started:
            self.pipeline.set_state(gst.STATE_NULL)
            self.pipeline.remove(self.asr)
            self.bus.disconnect(self.bus_id)
            self.started = False

    def shutdown(self):
        """ Delete any remaining parameters so they don't affect next launch """
        for param in [self._device_name_param, self._lm_param, self._dic_param]:
            if rospy.has_param(param):
                rospy.delete_param(param)

        """ Shutdown the GTK thread. """
        gtk.main_quit()

    def start(self, req):
        self.start_recognizer()
        rospy.loginfo("recognizer started")
        return EmptyResponse()

    def stop(self, req):
        self.stop_recognizer()
        rospy.loginfo("recognizer stopped")
        return EmptyResponse()

    def asr_partial_result(self, asr, text, uttid):
        """ Forward partial result signals on the bus to the main thread. """
        struct = gst.Structure('partial_result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        asr.post_message(gst.message_new_application(asr, struct))

    def asr_result(self, asr, text, uttid):
        """ Forward result signals on the bus to the main thread. """
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        asr.post_message(gst.message_new_application(asr, struct))

    def application_message(self, bus, msg):
        """ Receive application messages from the bus. """
        msgtype = msg.structure.get_name()
        if msgtype == 'partial_result':
            self.partial_result(msg.structure['hyp'], msg.structure['uttid'])
        if msgtype == 'result':
            self.final_result(msg.structure['hyp'], msg.structure['uttid'])

    def partial_result(self, hyp, uttid):
        """ Delete any previous selection, insert text and select it. """
        rospy.logdebug("Partial: " + hyp)

    def final_result(self, hyp, uttid):
        """ Insert the final result. """
	rospy.wait_for_service("topic_control")
	object_request = rospy.ServiceProxy("topic_control", tc)
        msg = String()
        msg.data = str(hyp.lower())
	global switch
        rospy.loginfo(msg.data)
	msg = str(msg)[6:]
	self.soundhandle.stopAll()
	if switch == True :
		if msg == 'robot stop':
			request = object_request(0)
			self.soundhandle.say('service stoped')
			self.pub.publish('service stoped')
			switch = False

		elif msg == 'finish robot':
#			request = object_request(-1)
			self.soundhandle.say('finishing service')
			sys.exit()

		else:
			self.switch_result(msg)

	else :
		if msg == 'robot start':
			self.pub.publish('start')
			request = object_request(1)
			self.soundhandle.say("i'm ready")
			switch = True
		
    def switch_result(self, msg):
	
	self.pub.publish(msg)
	global _pattern_rule, m
	m = _pattern_rule.match(msg.lower())
	if m is not None:
		self.pub.publish("pattern success")
		self.action(msg)
		self.count=0		
	elif self.count == 5 :
		self.soundhandle.stopAll()
		self.soundhandle.say('check the manual')
		self.pub.publish('check the manual')
		self.count=0
	else :
		self.soundhandle.say('speak again please')
		self.count += 1		

    def action(self, msg):
	rospy.wait_for_service('object_find')
	object_finder = rospy.ServiceProxy('object_find', stt)
	self.soundhandle.stopAll()	
	global _pattern_rule, m

	base_object=m.group(3)
	direction=m.group(2)
	self.pub.publish("recognized object : " + base_object)
	self.pub.publish("recognized direction : " + direction)
	object_f = object_finder(base_object, direction)
	object_f = str(object_f)[15:]
	if object_f == 'NONE':
		self.soundhandle.say('there is nothing')
	elif object_f.count(','):
		object_f = object_f.replace(",", " and ")
		self.soundhandle.say('there are ' + object_f)
	elif object_f == 'NOTDETECTED':
		self.soundhandle.say(base_object + 'is not detected')
		self.pub.publish(base_object + ' is not detected')
		return
	else :
		self.soundhandle.say('there is a ' + object_f)
	self.pub.publish('result object : ' + object_f)
	
	
if __name__ == "__main__":
    _pattern_rule = re.compile( '(what).*(right|left|under|upside).*(book|calendar|star).*')
    start = recognizer()
    gtk.main()

