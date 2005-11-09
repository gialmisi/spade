# -*- coding: cp1252 -*-
import sys
import xmpp
import threading
import thread
import Queue
import time
import MessageReceiver
import AID
import XMLCodec
import ACLParser
import Envelope
import ACLMessage
import BasicFipaDateTime
import Behaviour
import SL0Parser
#from AMS import AmsAgentDescription

class AbstractAgent(MessageReceiver.MessageReceiver):
    """
    Abstract Agent
    only for heritance
    Child classes: PlatformAgent, Agent
    """
    
    def __init__(self, agentjid, serverplatform):
	"""
	inits an agent with a JID (user@server) and a platform JID (acc.platformserver)
	"""
        MessageReceiver.MessageReceiver.__init__(self)
        self._aid = AID.aid(name=agentjid, addresses=[ "xmpp://acc."+serverplatform ])
        self._jabber = None
        self._serverplatform = serverplatform
        self._defaultbehaviour = None
        self._behaviourList = dict()
        self._isAlive = True



    def jabber_messageCB(self, conn, mess):
	"""
	message callback
	read the message envelope and post the message to the agent
	"""
        if (mess.getError() == None):
            envxml=None
            payload=mess.getBody()
            children = mess.getChildren()
            for child in children:
                if (child.getNamespace() == "jabber:x:fipa"):
                    envxml = child.getData()
            if (envxml != None):
                xc = XMLCodec.XMLCodec()
                ac =ACLParser.ACLParser()
		#print str(envxml)
                envelope = xc.parse(str(envxml))
                #print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
                #print payload
                #print "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

                ACLmsg = ac.parse(payload)
	        content = ACLmsg.getContent()
        	comillas_esc = '"'
	        barrainv_esc = '\\'
	        mtmp1 = comillas_esc.join(content.split('\\"'))
        	mtmp2 = barrainv_esc.join(mtmp1.split('\\\\'))
	        payload_esc = mtmp2
		ACLmsg.setContent(payload_esc)

                self.postMessage(ACLmsg)
            else:
                self.other_messageCB(conn,mess)


    def other_messageCB(self, conn, mess):
	"""
	non jabber:x:fipa chat messages callback
	"""
        pass

    
    def jabber_process(self):
	"""
	periodic jabber update
	"""
        while 1:
	    try:
	            self.jabber.Process(1)
	    except:
		    pass




    def getAID(self):
	"""
	returns AID
	"""
        return self._aid

    def getAMS(self):
	"""
	returns the AMS aid
	"""
        return AID.aid(name="ams." + self._serverplatform, addresses=[ "xmpp://acc."+self._serverplatform ])

    def getDF(self):
	"""
	returns the DF aid
	"""
        return AID.aid(name="df." + self._serverplatform, addresses=[ "xmpp://acc."+self._serverplatform ])

    def getSpadePlatformJID(self):
	"""
	returns the SPADE JID (string)
	"""
        return "acc." + self._serverplatform
    
    def send(self, ACLmsg):
	"""
	sends an ACLMessage
	"""
        self.sendTo(ACLmsg, self.getSpadePlatformJID())

    def sendTo(self, ACLmsg, tojid):
	"""
	sends an ACLMessage to a specific JabberID
	"""
        if (ACLmsg.getSender() == None):
            ACLmsg.setSender(self.getAID())

        content = ACLmsg.getContent()
        comillas_esc = '\\"'
        barrainv_esc = '\\\\'
        mtmp1 = barrainv_esc.join(content.split('\\'))
        mtmp2 = comillas_esc.join(mtmp1.split('"'))
        payload_esc = mtmp2
        ACLmsg.setContent(payload_esc)
        
        payload = str(ACLmsg)
        
        envelope = Envelope.Envelope()
        envelope.setFrom(ACLmsg.getSender())
        for i in ACLmsg.getReceivers():
            envelope.addTo(i)
        envelope.setAclRepresentation("fipa.acl.rep.string.std")
        envelope.setPayloadLength(len(payload))
        envelope.setPayloadEncoding("US-ASCII")
        envelope.setDate(BasicFipaDateTime.BasicFipaDateTime())

        
        xc = XMLCodec.XMLCodec()
        envxml = xc.encodeXML(envelope)

        xenv = xmpp.protocol.Node('jabber:x:fipa x')
        xenv['content-type']='fipa.mts.env.rep.xml.std'
        xenv.addData(envxml)
        
        jabber_msg = xmpp.protocol.Message(tojid,payload, xmlns="")
        jabber_msg.addChild(node=xenv)
        jabber_msg["from"]=self.getAID().getName()
        self.jabber.send(jabber_msg)
        #jabber_msg.setNamespace("jabber:component:accept")
        #print str(jabber_msg.getNamespace())
        #print str(jabber_msg.getAttrs())
        #print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
        #print jabber_msg
        #print "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
        
 


    
    def kill(self):
	"""
	kills the agent
	"""
        self._isAlive = False

    def isAlive(self):
	"""
	returns True if alive
	else False
	"""
        return self._isAlive
        
    def setup(self):
	"""
	setup agent method. configures the agent
	must be overridden
        """
        pass

    def takeDown(self):
	"""
	stops the agent
	must be overridden
        """
        pass

    def run(self):
	"""
	periodic agent execution
	"""
        #Init The agent
        self.setup()
        #Start the Behaviours
        if (self._defaultbehaviour != None):
            self._defaultbehaviour.start()
        #Main Loop
        try:
            while(self.isAlive()):
                #Check for new Messages form the server
                #self.jabber.Process(1)
                #Check for queued messages
                time.sleep(0)
                proc = False
                msg = self.blockingReceive(1)
                if (msg != None):
                    for b in self._behaviourList:
                        t = self._behaviourList[b]
                        if (t != None):
                            if (t.match(msg) == True):
                                b.postMessage(msg)
                                #if (b.done() == True):
                                #    self.removeBehaviour(b)
                                proc = True
                                break
                    if (proc == False):
                        if (self._defaultbehaviour != None):
                            self._defaultbehaviour.postMessage(msg)
            #Stop the Behaviours
            for b in self._behaviourList:
                self.removeBehaviour(b)
            if (self._defaultbehaviour != None):
                self._defaultbehaviour.kill()
            #DeInit the Agent
            self.takeDown()
        except:
            pass
            
    def start_and_wait(self):
	"""
	starts the agent and remains until the agent finishes
	"""

	self.start()
	try:
		while(self.isAlive()):
			time.sleep(1)
	except:
		pass

        
    def setDefaultBehaviour(self, behaviour):
	"""
	sets a Behavior as Default
	"""
        self._defaultbehaviour = behaviour
        behaviour.setAgent(self)

    def getDefaultBehaviour(self):
	"""
	returns the default behavior
	"""
        return self._defaultbehaviour

    def addBehaviour(self, behaviour, template=None):
	"""
	adds a new behavior to the agent
	"""
        self._behaviourList[behaviour] = template
        behaviour.setAgent(self)
        behaviour.start()

    def removeBehaviour(self, behaviour):
	"""
	removes a behavior from the agent
	"""
        try:
            self._behaviourList.pop(behaviour)
        except KeyError:
            pass
        behaviour.kill()

    class SearchAgentBehaviour(Behaviour.OneShotBehaviour):
        def __init__(self, msg, AAD, debug = False):
            Behaviour.OneShotBehaviour.__init__(self)
            self.AAD = AAD
            self.debug = debug
            self.result = None
            self.finished = False
            self._msg = msg

        def process(self):
            p = SL0Parser.SL0Parser()
            self._msg.addReceiver( self.myAgent.getAMS() )
            self._msg.setPerformative('request')
            self._msg.setLanguage('fipa-sl0')
            self._msg.setProtocol('fipa-request')
            self._msg.setOntology('FIPA-Agent-Management')
            
            content = "((action "
            content += str(self.myAgent.getAID())
            content += "(search "+ str(self.AAD) +")"
            content +=" ))"
            
            self._msg.setContent(content)
            self.myAgent.send(self._msg)
            msg = self.blockingReceive(10)
            if msg == None or msg.getPerformative() is not 'agree':
                print "There was an error searching the Agent. (not agree)"
                if self.debug:
                    print str(msg)
                self.finished = True
                return None
            msg = self.blockingReceive(20)
            if msg == None or msg.getPerformative() is not 'inform':
                print "There was an error searching the Agent. (not inform)"
                if self.debug:
                    print str(msg)
                self.finished = True
                return None
            else:
                content = p.parse(msg.getContent())
                if self.debug:
                    print str(msg)
                self.result = [] #content.result.set
		for i in content.result.set:
			#self.result.append(AmsAgentDescription(i)) #TODO: no puedo importar AMS :(
			#print str(i[1])
			self.result.append(i[1])
            self.finished = True

    def searchAgent(self, AAD, debug=False):
	"""
	searches an agent in the AMS
	the search template is an AmsAgentDescription class
	"""
        msg = ACLMessage.ACLMessage()
        template = Behaviour.ACLTemplate()
        template.setConversationId(msg.getConversationId())
        t = Behaviour.MessageTemplate(template)
        b = AbstractAgent.SearchAgentBehaviour(msg, AAD, debug)
        
        self.addBehaviour(b,t)
        b.join()
        return b.result
        
    
    class ModifyAgentBehaviour(Behaviour.OneShotBehaviour):
        def __init__(self, AAD, debug = False):
            Behaviour.OneShotBehaviour.__init__(self)
            self.AAD = AAD
            self.debug = debug
            self.result = None
            self.finished = False
            self._msg = ACLMessage()

        def process(self):
            p = SL0Parser.SL0Parser()
            self._msg.addReceiver( self.myAgent.getAMS() )
            self._msg.setPerformative('request')
            self._msg.setLanguage('fipa-sl0')
            self._msg.setProtocol('fipa-request')
            self._msg.setOntology('FIPA-Agent-Management')
            
            content = "((action "
            content += str(self.myAgent.getAID())
            content += "(modify "+ str(self.AAD) + ")"
            content +=" ))"

            self._msg.setContent(content)
            	
            self.myAgent.send(self._msg)

            msg = self.blockingReceive(20)
            if msg == None or msg.getPerformative() is not 'agree':
                print "There was an error modifying the Agent. (not agree)"
                if self.debug:
                    print str(msg)
                self.result = False
                return -1
            msg = self.blockingReceive(20)
            if msg == None or msg.getPerformative() is not 'inform':
                print "There was an error modifying the Agent. (not inform)"
                if self.debug:
                    print str(msg)
                self.result = False
                return -1
            self.result = True
            return 1

    def modifyAgent(self, AAD, debug=False):
	"""
	modifies the AmsAgentDescription of an agent in the AMS
	"""
        template = Behaviour.ACLTemplate()
        template.setConversationId(msg.getConversationId())
        t = Behaviour.MessageTemplate(template)
        b = AbstractAgent.ModifyAgentBehaviour(msg, AAD, debug)
        
        self.addBehaviour(b,t)
        b.join()
        return b.result


    class getPlatformInfoBehaviour(Behaviour.OneShotBehaviour):
        def __init__(self, msg, debug = False):
            Behaviour.OneShotBehaviour.__init__(self)
            self._msg = msg
            self.debug = debug
            self.result = None
            self.finished = False

	def process(self):
		msg = self._msg
		msg.addReceiver( self.myAgent.getAMS() )
		msg.setPerformative('request')
		msg.setLanguage('fipa-sl0')
		msg.setProtocol('fipa-request')
		msg.setOntology('FIPA-Agent-Management')
				
		content = "((action "
		content += str(self.myAgent.getAID())
		content += "(get-description platform)"
		content +=" ))"

		msg.setContent(content)
		
		self.myAgent.send(msg)

		msg = self.blockingReceive(20)
		if msg == None or msg.getPerformative() is not 'agree':
			print "There was an error modifying the Agent. (not agree)"
			if self.debug:
				print str(msg)
			return -1
		msg = self.blockingReceive(20)
		if msg == None or msg.getPerformative() is not 'inform':
			print "There was an error modifying the Agent. (not inform)"
			if self.debug:
				print str(msg)
			return -1

		self.result = msg.getContent()

    def getPlatformInfo(self, debug=False):
	"""
	returns the Plarform Info
	"""
	msg = ACLMessage.ACLMessage()
        template = Behaviour.ACLTemplate()
        template.setConversationId(msg.getConversationId())
        t = Behaviour.MessageTemplate(template)
        b = AbstractAgent.getPlatformInfoBehaviour(msg, debug)
        
        self.addBehaviour(b,t)
        b.join()
        return b.result
	

	##################################
    
    class registerServiceBehaviour(Behaviour.OneShotBehaviour):	    
    	def __init__(self, msg, DAD, debug = False):
            Behaviour.OneShotBehaviour.__init__(self)
            self._msg = msg
	    self.DAD = DAD
            self.debug = debug
            self.result = None
            self.finished = False

	def process(self):
		self._msg.addReceiver( self.myAgent.getDF() )
		self._msg.setPerformative('request')
		self._msg.setLanguage('fipa-sl0')
		self._msg.setProtocol('fipa-request')
		self._msg.setOntology('FIPA-Agent-Management')
				
		content = "((action "
		content += str(self.myAgent.getAID())
		content += "(register " + str(self.DAD) + ")"
		content +=" ))"

		self._msg.setContent(content)
		
		self.myAgent.send(self._msg)

		msg = self.blockingReceive(20)
		if msg == None or msg.getPerformative() is not 'agree':
			print "There was an error registering the Service. (not agree)"
			if self.debug:
				print str(msg)
			self.result = False
			return
		msg = self.blockingReceive(20)
		if msg == None or msg.getPerformative() is not 'inform':
			print "There was an error registering the Service. (not inform)"
			if self.debug:
				print str(msg)
			self.result = False
			return
	
		if self.debug:
			print str(msg)
		self.result = True

    def registerService(self, DAD, debug=False):
	"""
	registers a service in the DF
	the service template is a DfAgentDescriptor
	"""
	msg = ACLMessage.ACLMessage()
        template = Behaviour.ACLTemplate()
        template.setConversationId(msg.getConversationId())
        t = Behaviour.MessageTemplate(template)
        b = AbstractAgent.registerServiceBehaviour(msg=msg, DAD=DAD, debug=debug)
        
        self.addBehaviour(b,t)
        b.join()
        return b.result 
  
    class deregisterServiceBehaviour(Behaviour.OneShotBehaviour):
	def __init__(self, msg, DAD, debug=False):
            Behaviour.OneShotBehaviour.__init__(self)
            self._msg = msg
	    self.DAD = DAD
            self.debug = debug
            self.result = None
            self.finished = False

	def process(self):
		self._msg.addReceiver( self.myAgent.getDF() )
		self._msg.setPerformative('request')
		self._msg.setLanguage('fipa-sl0')
		self._msg.setProtocol('fipa-request')
		self._msg.setOntology('FIPA-Agent-Management')
				
		content = "((action "
		content += str(self.myAgent.getAID())
		content += "(deregister " + str(self.DAD) + ")"
		content +=" ))"

		self._msg.setContent(content)
		
		self.myAgent.send(self._msg)

		msg = self.blockingReceive(20)
		if msg == None or msg.getPerformative() is not 'agree':
			print "There was an error deregistering the Service. (not agree)"
			if self.debug:
				print str(msg)
			self.result = False
			return
		msg = self.blockingReceive(20)
		if msg == None or msg.getPerformative() is not 'inform':
			print "There was an error deregistering the Service. (not inform)"
			if self.debug:
				print str(msg)
			self.result = False
			return
	
		if self.debug:
			print str(msg)
		self.result = True
		return

    def deregisterService(self, DAD, debug=False):
	"""
	deregisters a service in the DF
	the service template is a DfAgentDescriptor
	"""
	msg = ACLMessage.ACLMessage()
        template = Behaviour.ACLTemplate()
        template.setConversationId(msg.getConversationId())
        t = Behaviour.MessageTemplate(template)
        b = AbstractAgent.deregisterServiceBehaviour(msg, DAD, debug)
        
        self.addBehaviour(b,t)
        b.join()
        return b.result 
  
    class searchServiceBehaviour(Behaviour.OneShotBehaviour):

	def __init__(self, msg, DAD, debug=False):
            Behaviour.OneShotBehaviour.__init__(self)
            self._msg = msg
	    self.DAD = DAD
            self.debug = debug
            self.result = None
            self.finished = False


	def process(self):	

		self._msg.addReceiver( self.myAgent.getDF() )
		self._msg.setPerformative('request')
		self._msg.setLanguage('fipa-sl0')
		self._msg.setProtocol('fipa-request')
		self._msg.setOntology('FIPA-Agent-Management')
				
		content = "((action "
		content += str(self.myAgent.getAID())
		content += "(search "+ str(self.DAD) +")"
		content +=" ))"
	
		self._msg.setContent(content)

		self.myAgent.send(self._msg)
	
		msg = self.blockingReceive(20)
		if msg == None or msg.getPerformative() is not 'agree':
			print "There was an error searching the Agent. (not agree)"
			if self.debug:
				print str(msg)
			return
		msg = self.blockingReceive(20)
		if msg == None or msg.getPerformative() is not 'inform':
			print "There was an error searching the Agent. (not inform)"
			if self.debug:
				print str(msg)
			return
	
		else:
			try:
				p = SL0Parser.SL0Parser()
				content = p.parse(msg.getContent())
				if self.debug:
					print str(msg)
				self.result = content.result.set#[0]#.asList()

			except:
				return
    def searchService(self, DAD, debug=False):
	"""
	search a service in the DF
	the service template is a DfAgentDescriptor
	"""
	msg = ACLMessage.ACLMessage()
        template = Behaviour.ACLTemplate()
        template.setConversationId(msg.getConversationId())
        t = Behaviour.MessageTemplate(template)
        b = AbstractAgent.searchServiceBehaviour(msg, DAD, debug)
        
        self.addBehaviour(b,t)
        b.join()
        return b.result 
  

    class modifyServiceBehaviour(Behaviour.OneShotBehaviour):
	def __init__(self, msg, DAD, debug=False):
            Behaviour.OneShotBehaviour.__init__(self)
            self._msg = msg
	    self.DAD = DAD
            self.debug = debug
            self.result = None

	def process(self):

		#p = SL0Parser.SL0Parser()
	
		self._msg = ACLMessage.ACLMessage()
		self._msg.addReceiver( self.myAgent.getDF() )
		self._msg.setPerformative('request')
		self._msg.setLanguage('fipa-sl0')
		self._msg.setProtocol('fipa-request')
		self._msg.setOntology('FIPA-Agent-Management')
				
		content = "((action "
		content += str(self.myAgent.getAID())
		content += "(modify "+ str(self.DAD) + ")"
		content +=" ))"

		self._msg.setContent(content)
		
		self.myAgent.send(self._msg)

		msg = self.blockingReceive(20)
		if msg == None or msg.getPerformative() is not 'agree':
			print "There was an error modifying the Service. (not agree)"
			if self.debug:
				print str(msg)
			self.result=False
			return
		msg = self.blockingReceive(20)
		if msg == None or msg.getPerformative() is not 'inform':
			print "There was an error modifying the Service. (not inform)"
			if self.debug:
				print str(msg)
			self.result = False
			return

		self.result = True
		return
    def modifyService(self, DAD, debug=False):
	"""
	modifies a service in the DF
	the service template is a DfAgentDescriptor
	"""
	msg = ACLMessage.ACLMessage()
        template = Behaviour.ACLTemplate()
        template.setConversationId(msg.getConversationId())
        t = Behaviour.MessageTemplate(template)
        b = AbstractAgent.modifyServiceBehaviour(msg, DAD, debug)
        
        self.addBehaviour(b,t)
        b.join()
        return b.result 


	##################################

class PlatformAgent(AbstractAgent):
    """
    A PlatformAgent is a SPADE component.
    Examples: AMS, DF, ACC, ...
    """
    def __init__(self, node, password, server="localhost", port=5347):
        AbstractAgent.__init__(self, node, server)
        self.jabber = xmpp.Component(server, port, debug=[])
        self._register(password)

    def _register(self, password, autoregister=True):
	"""
	registers the agent in the Jabber server
	"""

        jid = xmpp.protocol.JID(self._aid.getName())
        name = jid.getNode()

        #TODO: Que pasa si no conectamos? Hay que controlarlo!!!
        self.jabber.connect()
        

        if (self.jabber.auth(name,password,"spade") == None):
                raise NotImplementedError

        #print "auth ok", name
        thread.start_new_thread(self.jabber_process, tuple())
        self.jabber.RegisterHandler('message',self.jabber_messageCB)

class Agent(AbstractAgent):
    """
    This is the main class which may be inherited to build a SPADE agent
    """
    def __init__(self, agentjid, password, port=5222):
        jid = xmpp.protocol.JID(agentjid)
        self.server = jid.getDomain()
	self.port = port
        AbstractAgent.__init__(self, agentjid, self.server)
        self.jabber = xmpp.Client(self.server, self.port, debug=[])
        self._register(password)
        self.jabber.sendInitPresence()

    def _register(self, password, autoregister=True):
	"""
	registers the agent in the Jabber server
	"""

        jid = xmpp.protocol.JID(self._aid.getName())
        name = jid.getNode()

        #TODO: Que pasa si no conectamos? Hay que controlarlo!!!
        self.jabber.connect()
        

        #TODO:  Que pasa si no nos identificamos? Hay que controlarlo!!!
        #       Registrarse automaticamente o algo..
        #print "auth", name, password
        if (self.jabber.auth(name,password,"spade") == None):
            #raise NotImplementedError
	    
	    if (autoregister == True):
                #a=xmpp.features.getRegInfo(self.jabber,jid.getDomain())
		#print a
                b = xmpp.features.register(self.jabber,jid.getDomain(),\
		{'username':name, 'password':str(password)})

		#self.jabber.reconnectAndReauth()
		self.jabber.disconnect()
		del self.jabber
        	self.jabber = xmpp.Client(self.server, self.port, debug=[])
		self.jabber.connect()

                #print "--------------------------------> ", str(name)
                if (self.jabber.auth(name,password,"spade") == None):
                    raise NotImplementedError
            else:
                raise NotImplementedError
	    

        #print "auth ok", name
        thread.start_new_thread(self.jabber_process, tuple())
        self.jabber.RegisterHandler('message',self.jabber_messageCB)

    def run(self):
	"""
	Main loop of the agent
	registers in AMS, runs the agent and, finally, deregisters it from the AMS
	"""
	print "Registrando...."
        self.__register_in_AMS()
	print "Agent Registred!!!"
	AbstractAgent.run(self)
	print "Des-Registrando...."
        self.__deregister_from_AMS()


    def __register_in_AMS(self, state='active', ownership=None, debug=False):

	self._msg = ACLMessage.ACLMessage()
	self._msg.addReceiver( self.getAMS() )
	self._msg.setPerformative('request')
	self._msg.setLanguage('fipa-sl0')
	self._msg.setProtocol('fipa-request')
	self._msg.setOntology('FIPA-Agent-Management')
				
	content = "((action "
	content += str(self.getAID())
	content += "(register (ams-agent-description "
	content += ":name " + str(self.getAID())
	content += ":state "+state
	if ownership:
		content += ":ownership " + ownership
	content +=" ) ) ))"

	self._msg.setContent(content)
		
	self.send(self._msg)

	msg = self.blockingReceive(20)
	if msg == None or msg.getPerformative() is not 'agree':
		print "There was an error registering the Agent. (not agree)"
		if debug and msg != None:
			print str(msg)
		return -1
	msg = self.blockingReceive(20)
	if msg == None or msg.getPerformative() is not 'inform':
		print "There was an error registering the Agent. (not inform)"
		if debug and msg != None:
			print str(msg)
		return -1
	
	if debug and msg != None:
		print str(msg)
	return 1

    def __deregister_from_AMS(self, state=None, ownership=None, debug=False):
	self._msg = ACLMessage.ACLMessage()
	self._msg.addReceiver( self.getAMS() )
	self._msg.setPerformative('request')
	self._msg.setLanguage('fipa-sl0')
	self._msg.setProtocol('fipa-request')
	self._msg.setOntology('FIPA-Agent-Management')
				
	content = "((action "
	content += str(self.getAID())
	content += "(deregister (ams-agent-description "
	content += " :name " + str(self.getAID())
	if state:
		content += " :state "+state
	if ownership:
		content += " :ownership " + ownership
	content +=" ) ) ))"

	self._msg.setContent(content)
		
	self.send(self._msg)

	msg = self.blockingReceive(20)
	if msg == None or msg.getPerformative() is not 'agree':
		sys.stdout.write("There was an error deregistering the Agent.\n")
		if debug:
			sys.stdout.write(str(msg))
		return -1
	msg = self.blockingReceive(20)
	if msg == None or msg.getPerformative() is not 'inform':
		sys.stdout.write("There was an error deregistering the Agent.\n")
		if debug:
			sys.stdout.write(str(msg))
		return -1
	
	if debug:
		sys.stdout.write(str(msg))
	return 1


