#######################################################
# 
# ReceiveConnections.py
# Python implementation of the Class ReceiveConnections
# Generated by Enterprise Architect
# Created on:      19-May-2020 6:21:05 PM
# Original author: Natha Paquette
# 
#######################################################
import asyncio
import socket
import logging
import logging.handlers
import re
from lxml import etree
import time
import os
from typing import Union

from FreeTAKServer.core.configuration.ClientReceptionLoggingConstants import ClientReceptionLoggingConstants
from FreeTAKServer.core.configuration.LoggingConstants import LoggingConstants
from FreeTAKServer.model.RawConnectionInformation import RawConnectionInformation as sat
from FreeTAKServer.core.configuration.CreateLoggerController import CreateLoggerController
from FreeTAKServer.core.configuration.ReceiveConnectionsConstants import ReceiveConnectionsConstants
from FreeTAKServer.model.RawConnectionInformation import RawConnectionInformation

loggingConstants = LoggingConstants(log_name="FTS_ReceiveConnections")
logger = CreateLoggerController("FTS_ReceiveConnections", logging_constants=loggingConstants).getLogger()

loggingConstants = ClientReceptionLoggingConstants()

TEST_SUCCESS = "success"
END_OF_MESSAGE = b"</event>"

# TODO: move health check values to constants and create controller for HealthCheck data

class ReceiveConnections:
    connections_received = 0

    def receive_connection_data(self, client) -> Union[etree.Element, str]:
        """this method is responsible for receiving connection data from the client

        Args:
            client (socket.socket): _description_

        Raises:
            Exception: if data returned by client is empty

        Returns:
            Union[etree.Element, str]: in case of real connection an etree Element should be returned containing client connection data
                                        in case of test connection TEST_SUCCESS const should be returned
        """        
        client.settimeout(int(ReceiveConnectionsConstants().RECEIVECONNECTIONDATATIMEOUT))
        part = client.recv(1)
        if part == b"": raise Exception('empty data')
        client.settimeout(10)
        client.setblocking(True)
        xmlstring = self.recv_until(client, b"</event>").decode()
        if part.decode()+xmlstring == ReceiveConnectionsConstants().TESTDATA: return TEST_SUCCESS
        client.setblocking(True)
        client.settimeout(int(ReceiveConnectionsConstants().RECEIVECONNECTIONDATATIMEOUT))
        xmlstring = "<multiEvent>" + part.decode() + xmlstring + "</multiEvent>"  # convert to xmlstring wrapped by multiEvent tags
        xmlstring = re.sub(r'(?s)\<\?xml(.*)\?\>', '',
                           xmlstring)  # replace xml definition tag with empty string as it breaks serilization
        events = etree.fromstring(xmlstring)
        return events

    def listen(self, sock: socket.socket) -> Union[RawConnectionInformation, int]:
        """
        Listen for incoming client connections and process them.

        This method listens for incoming client connections, receives data from the
        client, and then instantiates a client object with the received data. If
        any errors occur during this process, the method returns -1. Otherwise, it
        returns the instantiated client object.

        Parameters
        ----------
        sock : socket.socket
            The socket to listen for incoming connections on.

        Returns
        -------
        Union[RawConnectionInformation, int]
            The instantiated client object, or -1 if any errors occurred.
        """

        # logger = CreateLoggerController("ReceiveConnections").getLogger()

        # Listen for client connections
        sock.listen(ReceiveConnectionsConstants().LISTEN_COUNT)

        try:
            # Accept a client connection
            client, address = sock.accept()

            # Receive data from the client
            try:
                events = self.receive_connection_data(client=client)
            except Exception as e:
                try:
                    events = self.receive_connection_data(client=client)
                except Exception as e:
                    client.close()
                    logger.warning("Receiving connection data from client failed with exception " + str(e))
                    return -1

            # Set the socket to non-blocking
            client.settimeout(0)

            # Log that a client was accepted
            logger.info(loggingConstants.RECEIVECONNECTIONSLISTENINFO)

            # Instantiate a client object with the received data
            raw_connection_information = self.instantiate_client_object(address, client, events)
            logger.info("Client accepted")

            # Return the client object if it is valid, or -1 if it is not
            try:
                if sock is not None and raw_connection_information.xmlString != b'':
                    return raw_connection_information
                else:
                    logger.warning("Final socket entry is invalid")
                    client.close()
                    return -1
            except Exception as e:
                client.close()
                logger.warning('Exception in returning data ' + str(e))
                return -1
                
        except Exception as e:
            logger.warning(loggingConstants.RECEIVECONNECTIONSLISTENERROR)
            try:
                client.close()
            except Exception as e:
                pass
            finally:
                return -1


    def instantiate_client_object(self, address, client, events):
        raw_connection_information = sat()
        raw_connection_information.ip = address[0]
        raw_connection_information.socket = client
        raw_connection_information.xmlString = etree.tostring(events.findall('event')[0]).decode('utf-8')
        return raw_connection_information

    def recv_until(self, client, delimiter) -> bytes:
        """receive data until a delimiter has been reached

        Args:
            client (socket.socket): client socket
            delimiter (bytes): bytestring representing the delimiter

        Returns:
            Union[None, bytes]: None if no data was received otherwise send received data
        """        
        message = b""
        start_receive_time = time.time()
        client.settimeout(4)
        while delimiter not in message and time.time() - start_receive_time <= ReceiveConnectionsConstants().RECEIVECONNECTIONDATATIMEOUT:
            try:
                message = message + client.recv(ReceiveConnectionsConstants().CONNECTION_DATA_BUFFER)
            except:
                return message
        return message
