#!/usr/bin/env python2.7
"""
Python module for interacting with Universal Devices ISY994 Insteon/ZWave controller hub
"""

import collections
import datetime
import json
import requests
#from xml.etree import ElementTree
import xmltodict
from StringIO import StringIO
import types

# Patch the json module to handle python dattime objects
json.JSONEncoder.default = lambda self, obj: (obj.isoformat() if isinstance(obj, datetime.datetime) else None)

class ISYError(Exception):
    """Base exception for all ISY related errors"""

class ISYObjectNotFound(ISYError):
    """Exception thrown when an object could not be found"""
    def __init__(self, nodeName):
        super(ISYObjectNotFound, self).__init__("Object '{}' could not be found".format(nodeName))

class ISYCommandFailed(ISYError):
    """Exception thrown when a command fails"""
    def __init__(self, cmd, nodeName):
        super(ISYCommandFailed, self).__init__("Command '{}' to '{}' failed".format(cmd, nodeName))

class ISYController(object):
    """
    This object represents the ISY 994 controller
    """

    def __init__(self, ipAddress, username, password, useHTTPS=False, ignoreCert=False):
        """
        Create an ISYController object

        Args:
            ipAddress:      the ISY IP/hostname.  include :port to use a customer port
            username:       the ISY username
            password:       the ISY password
            userHTTPS:      use https instead of http
            ignoreCert:     if using https, ignore invalid certs
        """
        self.ip = ipAddress
        self.username = username
        self.password = password
        self.useHTTPS = useHTTPS
        self.verifyCert = not ignoreCert

    def _ControllerRequest(self, url):
        """
        Send a GET request to the controller REST endpoint

        Args:
            url:    the URL piece to send the request to (str)

        Returns:
            The response parsed to a dictionary (dict)
        """
        result = requests.get("{}://{}/rest/{}".format("https" if self.useHTTPS else "http",
                                                       self.ip,
                                                       url),
                              auth=(self.username, self.password),
                              verify=self.verifyCert)
#        print result.headers
#        print result.text
 
        # Convert XML to dictionary
        res = xmltodict.parse(result.text)

        # Convert from OrderedDict to dict
        res = json.loads(json.dumps(res))

        XMLHelper.AttrToMember(res)

        return res

    def ListAllNodes(self):
        """
        Get a list of nodes and groups that this controller knows about

        Returns:
            A python dictionary with the nodes/groups (dict)
        """
        res = self._ControllerRequest("nodes")
        res = res["nodes"]

        # Transform the result to more python dict/JSON-like instead of XML-like
        res.pop("root", None)

        if "group" not in res:
            res["group"] = []
        res["groups"] = res.pop("group")

        if "node" not in res:
            res["node"] = []
        res["nodes"] = res.pop("node")

#        print res

        for node in res["nodes"]:
            ISYDataHelpers.TransformNode(node)
        for group in res["groups"]:
            ISYDataHelpers.TransformGroup(group)

        return res

    def ListAllPrograms(self):
        """
        Get a list of all programs defined on this controller

        Returns:
            A list of programs (list of dict)
        """
        res = self._ControllerRequest("programs?subfolders=true")
        res = res["programs"]["program"]
        for prog in res:
            ISYDataHelpers.TransformProgram(prog)
        
        return res

    def GetNode(self, name=None, address=None, searchKey=None):
        """
        Get a node (device or group) by name or address

        Args:
            name:       the name of the node to find (str)
            address:    the address of hte node to find (str)
            searchKey:  optional subkey to search instead of all of them (str)

        Returns:
            A dictionary of the node's properties (dict)
        """
        all_nodes = self.ListAllNodes()
        if searchKey:
            search_nodes = all_nodes[searchKey]
        else:
            search_nodes = all_nodes["nodes"] + all_nodes["groups"]

        for node in search_nodes:
            if name and node["name"] == name:
                return node
            if address and node["address"] == address:
                return node

        raise ISYObjectNotFound(name)

    def NodeCommand(self, nodeAddress, command):
        """
        Run a command against a node

        Args:
            nodeAddress:    the address of the node
            command:        the command to run
        """
        result = self._ControllerRequest("nodes/{}/cmd/{}".format(nodeAddress, command))
        XMLHelper.StringToNumber(result)
        if not result["RestResponse"]["succeeded"]:
            raise ISYCommandFailed(command, nodeAddress)

    def GetDevice(self, name=None, address=None):
        """
        Get a device attached to this controller, either by name or by address

        Args:
            name:       the name of the device
            address:    the address of the device

        Returns:
            An ISY device object (ISYDevice)
        """
        if not name and not address:
            raise ValueError("You must specify either name or address")

        return ISYDevice(self.GetNode(name=name, address=address, searchKey="nodes"), self)

    def GetProgram(self, name):
        """
        Get a program defined in this controller

        Args:
            name:   the name of the program

        Returns:
            An ISY program object (ISYProgram)
        """
        all_programs = self.ListAllPrograms()
        for prog in all_programs:
            if prog["folder"]:
                continue
            if prog["name"] == name:
                return ISYProgram(prog, self)

        raise ISYObjectNotFound(name)

    def ProgramCommand(self, programID, command):
        """
        Runa a command against a program

        Args:
            programID:      the ID of the pgroam to run
            command:        the command to run
        """
        result = self._ControllerRequest("programs/{}/{}".format(programID, command))
        XMLHelper.StringToNumber(result)
        if not result["RestResponse"]["succeeded"]:
            raise ISYCommandFailed(command, programID)

class ISYDevice(object):
    """
    This object represents a device connected to the ISY controller
    """

    def __init__(self, deviceProperties, controller):
        """
        This object should not be instantiated directly, instead use ISYController.GetDevice
        """
        self.controller = controller
        self.properties = deviceProperties
        
        self.address = self.properties["address"]
        self.name = self.properties["name"]

    def __repr__(self):
        return "{}({})".format(type(self).__name__, ISYDataHelpers.StringifyDict(self.properties))

    def __str__(self):
        return "{}({}, {})".format(type(self).__name__, self.name, self.address)

    def GetState(self):
        """
        Get the state of this device

        Returns:
            The state (str)
        """
        for prop in self.properties["properties"]:
            if prop["id"] == "ST":
                return prop["value"]

    def TurnOn(self, level=100):
        """
        Turn this device on

        Args:
            level:  the level to turn on to, as a percent (int)
        """
        onamount = level * 255 / 100
        self.controller.NodeCommand(self.address, "DON/{}".format(onamount))

    def TurnOff(self):
        """
        Turn this device off
        """
        self.controller.NodeCommand(self.address, "DOF")


class ISYScene(ISYDevice):
    """
    This object represents a scene defined in the ISY controller
    """

class ISYProgram(object):
    """
    This object represents a program defined in the ISY controller
    """

    def __init__(self, programProperties, controller):
        """
        This object should not be instantiated directly, instead use ISYController.GetProgram
        """
        self.properties = programProperties
        self.controller = controller
        self.ID = self.properties["id"]
        self.name = self.properties["name"]

    def __repr__(self):
        return "{}({})".format(type(self).__name__, ISYDataHelpers.StringifyDict(self.properties))

    def __str__(self):
        return "{}({}, {})".format(type(self).__name__, self.name, self.ID)

    def Run(self):
        """
        Run this program
        """
        self.controller.ProgramCommand(self.ID, "run")

    def RunThen(self):
        """
        Run the "then" clause of this program
        """
        self.controller.ProgramCommand(self.ID, "runThen")

    def RunElse(self):
        """
        Run the "else" clause of this program
        """
        self.controller.ProgramCommand(self.ID, "runElse")


class XMLHelper(object):
    """
    Collection of methods to help transform XML into useful python dictionaries
    """

    @staticmethod
    def AttrToMember(xmldict):
        """
        Recurrsively search a dictionary and rename any "@key" to "key"

        Args:
            xmldict:    the dictionary to transform (dict)
        """

        # Short-circuit for strings, otherwise they will test True on Iterable
        if isinstance(xmldict, basestring):
            return

        # Go through each dictionary element and rename the keys if necessary
        elif isinstance(xmldict, types.DictionaryType):
            allkeys = xmldict.keys()

            # Rename any @keys
            for key in allkeys:
                if key.startswith("@"):
                    xmldict[key[1:]] = xmldict.pop(key)
            # Recurse down
            for key in xmldict.keys():
                XMLHelper.AttrToMember(xmldict[key])

        elif isinstance(xmldict, collections.Iterable):
            for value in xmldict:
                XMLHelper.AttrToMember(value)

    @staticmethod
    def TextToMember(xmldict, memberName):
        """
        Convert #text keys to a better name

        Args:
            xmldict:        the dictionary to transform (dict)
            memberName:     the new name for the #text keys (str)
        """
        if "#text" not in xmldict:
            return
        xmldict[memberName] = xmldict.pop("#text")

    @staticmethod
    def StringToNumber(xmldict, skipKeys=None):
        """
        Recursively search a dictionary and convert string values that look like bool, float or int, into their actual types

        Args:
            xmldict:        the dictionary to transform (dict)
            skipKeys:       a list of keys to skip transforming (list of str)
        """
        if isinstance(xmldict, basestring):
            temp = XMLHelper._AttemptStrToBool(xmldict)
            return XMLHelper._AttemptStrToNum(temp)
        if isinstance(xmldict, types.DictionaryType):
            for key in xmldict.iterkeys():
                if isinstance(xmldict[key], basestring):
                    if skipKeys and key in skipKeys:
                        continue
                    xmldict[key] = XMLHelper._AttemptStrToBool(xmldict[key])
                    xmldict[key] = XMLHelper._AttemptStrToNum(xmldict[key])
                else:
                    XMLHelper.StringToNumber(xmldict[key], skipKeys)
        elif isinstance(xmldict, collections.Iterable):
            for idx, value in enumerate(xmldict):
                if isinstance(value, basestring):
                    xmldict[idx] = XMLHelper._AttemptStrToBool(value)
                    xmldict[idx] = XMLHelper._AttemptStrToNum(value)
                else:
                    XMLHelper.StringToNumber(value, skipKeys)

    @staticmethod
    def _AttemptStrToNum(value):
        """
        Internal function to convert a string to a number (float or int).  If the value is not a valid number,
        it is returned unmodified

        Args:
            value:  the value to convert (str)

        Returns:
            the possibly converted value (int or float or str)
        """
        if not isinstance(value, basestring):
            return value

        before = value
        after = value
        if "." in value:
            try:
                after = float(value)
            except ValueError:
                pass
        else:
            try:
                after = int(value)
            except ValueError:
                pass
#        print "before={} after={}".format(before, after)
        assert before == str(after)
        return after

    @staticmethod
    def _AttemptStrToBool(value):
        """
        Internal function to convert a string to a boolean. If the value is not true or false, it is returned unmodified

        Args:
            value:  the value to convert (str)

        Returns:
            the possibly converted value (bool or str)
        """
        if not isinstance(value, basestring):
            return value

        before = value
        after = value
        if value.lower() == "true":
            after = True
        elif value.lower() == "false":
            after = False
#        print "before={} after={}".format(before, after)
        assert before.lower() == str(after).lower()
        return after

    @staticmethod
    def EnsureMember(xmldict, key, valtype):
        """
        Ensure that a dictionary has a key

        Args:
            xmldict:    the dictionary to transform (dict)
            key:        the name of the key to check for
            valtype:    the type to create the key as if it does not exist
        """
        if key not in xmldict or not xmldict[key]:
            xmldict[key] = valtype()

class ISYDataHelpers(object):
    """
    Collection of helper methods for data objects
    """

    @staticmethod
    def TransformNode(node):
        """
        Transform a node dictionary from XML-ish to more usable format

        Args:
            node:   the node to transform(dict)
        """
        XMLHelper.AttrToMember(node)
        XMLHelper.EnsureMember(node, "property", list)
        node["properties"] = node.pop("property")
        if isinstance(node["properties"], types.DictionaryType):
            node["properties"] = [node["properties"]]
        for prop in node["properties"]:
            prop["rawvalue"] = prop.pop("value")
            prop["value"] = prop.pop("formatted").strip()
            prop["name"] = prop["id"].strip()
            if prop["value"] == "":
                prop["value"] = None
            if prop["id"] == "ST":
                prop["name"] = "State"
        XMLHelper.StringToNumber(node, skipKeys=["address"])

    @staticmethod
    def TransformGroup(group):
        """
        Transform a group dictionary from XML-ish to more usable format

        Args:
            group:   the group to transform(dict)
        """
        XMLHelper.AttrToMember(group)
        XMLHelper.EnsureMember(group, "members", dict)
        XMLHelper.EnsureMember(group["members"], "link", list)
        group["members"] = group["members"]["link"]
        for link in group["members"]:
            XMLHelper.TextToMember(link, "address")
        XMLHelper.StringToNumber(group, skipKeys=["address"])

    @staticmethod
    def TransformProgram(prog):
        """
        Transform a program dictionary from XML-ish to more usable format

        Args:
            prog:   the program to transform(dict)
        """
        XMLHelper.StringToNumber(prog, skipKeys=["id", "parentId"])
        for key in ("lastFinishTime", "lastRunTime", "nextScheduledRunTime"):
            if key in prog:
                prog[key] = ISYDataHelpers.StringToDate(prog[key])

    @staticmethod
    def StringifyDict(stringify):
        """
        Recursively create a human readable string representation of a dictionary

        Args:
            stringify:  the dictionary to stringify (dict)

        Returns:
            A string representation of the dictionary (str)
        """
        buff = StringIO()
        buff.write("{")
        for key, value in sorted(stringify.items()):
            buff.write("{}=".format(key))
            if isinstance(value, basestring):
                buff.write(value)
            elif isinstance(value, types.DictionaryType):
                buff.write("{")
                buff.write(ISYDataHelpers.StringifyDict(value))
                buff.write("}")
            elif isinstance(value, collections.Iterable):
                buff.write("[")
                for item in value:
                    buff.write(ISYDataHelpers.StringifyDict(item))
                buff.write("]")
            else:
                buff.write(str(value))
            buff.write(", ")
        out = buff.getvalue()[:-2]
        return out + "}"

    @staticmethod
    def StringToDate(value):
        """
        Convert a string in ISY format to a datetime object

        Args:
            value:  the date string to convert (str)

        Returns:
            The converted date (datetime)
        """
        if not value:
            return None
        value = value.replace("  ", " 0")
        return datetime.datetime.strptime(value, "%Y/%m/%d %I:%M:%S %p")


if __name__ == '__main__':
    import time
    
    # Disable SSL warning from requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    isy = ISYController("192.168.1.121", "admin", "zGnC3reu9v")
#    isy = ISYController("cseelye.asuscomm.com:4343", "admin", "zGnC3reu9v", useHTTPS=True, ignoreCert=True)

    # prog = isy.GetProgram("testprog")
    # prog.RunElse()
    # time.sleep(10)
    # prog.Run()

#    print json.dumps(isy.ListAllPrograms(), sort_keys=True, indent=4)

    dev = isy.GetDevice(name="Couch lamps")
    print repr(dev)

#    print isy._ControllerRequest("nodes/40%20E6%2083%201/cmd/DOFF/255")
#    print json.dumps(isy.GetNodeByName("Front lights"), sort_keys=True, indent=4)

