import time
import select
import socket
import threading
import random
import json
import sys
import re
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QMessageBox, QTableWidgetItem
from PyQt5.QtCore import *
from ClientMainUI import *


class Channel():
    def __init__(self, name, socket, server):
        self.name = name
        self.socket = socket
        self.server = server

    def sendMessage(self, text):
        matchObj = re.match(r'@(.*?):(.*?):(.*?)', text, re.S | re.M)
        message = {}
        message['From'] = self.socket.getsockname()
        if matchObj:
            message['To'] = (matchObj.group(1), int(matchObj.group(2)))
            message['Data'] = text[len(matchObj.group(0)):]
        else:
            message['To'] = 'all'
            message['Data'] = text
        JsonData = json.dumps(message).encode('utf-8')
        try:
            print('Sending Messages:{} '.format(message))
            self.socket.sendto(JsonData, self.server)
        except:
            print('error!')
            return False
        return True


class Client():

    def __init__(self, MainWindow):
        self.MainWindow = MainWindow
        self.MainFrame = MainWindow.ui_Window  # UI interface

        self.localIP = '127.0.0.1'  # local IP

        self.host = '127.0.0.1'  # server IP
        self.port = 5000

        self.current_channel_name = ''
        self.udpSocket = None  # current socket
        self.udpPort = 0  # current port
        self.channel = None

        self.socket_list = []
        self.channels = []

        self.tcpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcpSocket.settimeout(3)
        try:
            self.tcpSocket.connect((self.host, self.port))
        except socket.error as e:
            print('Unable to connect')
            self.status = False
            self.tcpSocket = None
            self.MainFrame.pushButton.setEnabled(False)
            self.MainFrame.label_2.setText('Failure')
        else:
            print('Connected to remote host')
            self.status = True
            self.MainFrame.label_2.setText('Succeed')
            # start listening
            self.socket_list.append(self.tcpSocket)
            self.t = threading.Thread(target=self.run, args=(self.MainWindow.signal,),)
            self.t.setDaemon(True)
            self.t.start()
            # get channel list
            self.getList()

    def run(self, signal):
        # start listening
        while self.socket_list:
            # Get the list sockets which are readable
            read_sockets, write_sockets, error_sockets = select.select(self.socket_list, [], [])
            for sock in read_sockets:
                # incoming message from remote server
                if sock == self.tcpSocket:
                    try:
                        data = sock.recv(4096)
                    except:
                        print('TCP Error')
                    else:
                        if not data:
                            print('Disconnected from chat server')
                            self.tcpSocket.shutdown(socket.SHUT_RDWR)
                            self.tcpSocket = None
                            self.socket_list = []
                            self.MainFrame.label_2.setText('Failure')
                            self.MainFrame.pushButton.setEnabled(False)
                            signal.emit('MessageBox')
                        else:
                            message = json.loads(data.decode())
                            if message['Head'] == 'CHANNELSLIST':
                                self.channels = message['Data']
                                print(self.channels)
                                self.updatechannelsList()
                            if message['Head'] == 'USERLIST' and message['channel'] == self.current_channel_name:
                                userList = message['Data']
                                self.MainFrame.listWidget_3.clear()
                                for user in userList:
                                    title = '{}:{}'.format(user[0], user[1])
                                    self.MainFrame.listWidget_3.addItem(title)
                            if message['Head'] == 'EXIT SERVER':
                                print('Disconnected from chat server')
                                self.tcpSocket.shutdown(socket.SHUT_RDWR)
                                self.tcpSocket = None
                                self.socket_list = []
                                self.MainFrame.label_2.setText('Failure')
                                self.MainFrame.pushButton.setEnabled(False)
                                signal.emit('MessageBox')
                else:
                    # UDP datas
                    try:
                        data = sock.recv(4096)
                    except:
                        pass
                    else:
                        message = json.loads(data.decode())
                        if message['To'] != 'all':
                            str_message = '[Private] {}:{}：   {}'.format(message['From'][0], message['From'][1], message['Data'])
                        else:
                            str_message = '[All] {}:{}：   {}'.format(message['From'][0], message['From'][1], message['Data'])
                            if message['Data'] == '{}:{} Exit Channel.'.format(self.localIP, self.udpPort):
                                self.MainFrame.listWidget.clear()
                                self.socket_list.remove(self.udpSocket)
                                self.udpSocket = None
                                self.channel = None
                                time.sleep(1)
                        self.MainFrame.listWidget.addItem(str_message)
                        if message['Data'] == 'channel is closed!.':
                            self.channel = None
                            self.socket_list.remove(self.udpSocket)
                            self.udpSocket = None
                    
    def getList(self):
        print('Sending Messages GET')
        self.tcpSocket.sendall(b'GET')

    def updatechannelsList(self):
        self.MainFrame.listWidget_2.clear()
        for channel in self.channels:
            title = '{:<10s}{:>10s}'.format(channel['name'], channel['Theme'])
            self.MainFrame.listWidget_2.addItem(title)

    def leaveChannel(self, text):
        name = text.split(' ')[0].strip()
        if self.udpSocket != None:
            reply = QMessageBox.question(self.MainWindow, 'Info', 'You are leaving Channel {0}. Are you sure?'.format(self.current_channel_name),
                                         QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                print('Quit Channel: ' + name)
                self.MainFrame.listWidget.clear()
                message = 'QUIT {name} {ip} {port}'.format(name=self.current_channel_name, ip=self.localIP, port=self.udpPort)
                self.tcpSocket.sendall(message.encode('utf-8'))
                self.socket_list.remove(self.udpSocket)
                self.udpSocket = None
                self.channel = None
                time.sleep(1)
            else:
                return self.channel
        else:
            QMessageBox.question(self.MainWindow, 'Info',
                                             'You have to enter a Channel first.')
        self.MainFrame.groupBox_2.setTitle('Channel')

    def enterChannel(self, text):
        name = text.split(' ')[0].strip()
        if self.udpSocket != None:
            if name != self.current_channel_name:
                reply = QMessageBox.question(self.MainWindow, 'Info', 'You need to quit Channel {0} first. Are you sure?'.format(self.current_channel_name),
                                             QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    print('Quit Channel: ' + name)
                    self.MainFrame.listWidget.clear()
                    message = 'QUIT {name} {ip} {port}'.format(name= self.current_channel_name, ip=self.localIP, port=self.udpPort)
                    self.tcpSocket.sendall(message.encode('utf-8'))
                    self.socket_list.remove(self.udpSocket)
                    self.udpSocket = None
                    time.sleep(1)
                else:
                    return self.channel
        self.MainFrame.groupBox_2.setTitle('Channel:' + name)
        if name != self.current_channel_name:
            print('Enter Channel: ' + name)
            self.udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udpPort = random.randint(3000, 6000)
            self.udpSocket.bind((self.localIP, self.udpPort))
            self.current_channel_name = name
            self.socket_list.append(self.udpSocket)

            for channel in self.channels:
                if channel['name'] == name:
                    self.serverUdpAddr = (self.host, channel['port'])
                    message = 'ENTER {name} {ip} {port}'.format(name=name, ip=self.localIP, port=self.udpPort)
                    self.tcpSocket.sendall(message.encode('utf-8'))
                    self.channel = Channel(name, self.udpSocket, self.serverUdpAddr)
                    return self.channel
        else:
            return self.channel
        return self.channel

    def exitAPP(self):
        print('Sending Messages EXIT')
        self.socket_list = []
        if self.tcpSocket != None:
            message = 'EXIT {name} {ip} {port}'.format(name = self.current_channel_name, ip= self.localIP, port= self.udpPort)
            self.tcpSocket.sendall(message.encode('utf-8'))

class ClientWindowDlg(QMainWindow):

    signal = pyqtSignal(str)  # signal def

    def __init__(self):
        super(ClientWindowDlg, self).__init__()
        self.ui_Window = Ui_MainWindow()
        self.ui_Window.setupUi(self)
        self.signal.connect(self.MessageBox)  #
        self.client = Client(self)
        self.channel = None  #

    def closeEvent(self, *args, **kwargs):
        self.client.exitAPP()

    def MessageBox(self):
        reply = QMessageBox.information(self, 'Info',
                                     'Disconnected from chat server!', QMessageBox.Yes)

    def sendMessage(self):
        if self.client.channel != None:
            text = self.ui_Window.plainTextEdit.toPlainText()
            matchObj = re.match(r'@(.*?):(.*?):(.*?)', text, re.S | re.M)
            if matchObj:
                str_message = '[Private] {}:{}：   {}'.format(matchObj.group(1), int(matchObj.group(2)), text[len(matchObj.group(0)):])
                self.client.MainFrame.listWidget.addItem(str_message)

            self.channel.sendMessage(self.ui_Window.plainTextEdit.toPlainText())
            self.ui_Window.plainTextEdit.clear()
        else:
            reply = QMessageBox.information(self, 'Info', 'You need to enter a Channel first.',
                                         QMessageBox.Yes)

    def leaveChannel(self):
        if self.client.channel != None:
            # print(self.client.channel.name)
            self.client.leaveChannel(self.client.channel.name)
        else:
            reply = QMessageBox.information(self, 'Info', 'You need to enter a Channel first.',
                                         QMessageBox.Yes)

    def clickUserList(self, item):
        user = item.text()
        self.ui_Window.plainTextEdit.setPlainText('@' + user + ": ")

    def enterChannel(self, item):
        channel = item.text()
        self.channel = self.client.enterChannel(channel)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWindow = ClientWindowDlg()
    mainWindow.show()
    sys.exit(app.exec_())