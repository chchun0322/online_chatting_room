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


class Room():
    def __init__(self, name, socket, server):
        self.name = name
        self.socket = socket
        self.server = server

    def sendMessage(self, text):
        marchtObj = re.match(r'@(.*?):(.*?):(.*?)', text, re.S | re.M)
        message = {}
        message['From'] = self.socket.getsockname()
        if marchtObj:
            message['To'] = (marchtObj.group(1), int(marchtObj.group(2)))
            message['Data'] = text[len(marchtObj.group(0)):]
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
        self.room = None

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
            # get room list
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
                        # addr = sock.getpeername()
                        print('UDP recive: {data}'.format(data = data ) )
                        message = json.loads(data.decode())
                        if message['To'] != 'all':
                            str_message = '[Private] {}:{}：   {}'.format(message['From'][0], message['From'][1], message['Data'])
                        else:
                            str_message = '[All] {}:{}：   {}'.format(message['From'][0], message['From'][1], message['Data'])
                            if message['Data'] == '{}:{} Exit Room.'.format(self.localIP, self.udpPort):
                                self.MainFrame.listWidget.clear()  # 清空消息列表
                                self.socket_list.remove(self.udpSocket)
                                self.udpSocket = None
                                self.room = None
                                time.sleep(1)
                        self.MainFrame.listWidget.addItem(str_message)
                        if message['Data'] == 'channel is closed!.':
                            self.room = None
                            self.socket_list.remove(self.udpSocket)
                            self.udpSocket = None
                    
    def getList(self):
        print('Sending Messages GET')
        self.tcpSocket.sendall(b'GET')

    def updatechannelsList(self):
        self.MainFrame.listWidget_2.clear()  # 聊天室列表
        for channel in self.channels:
            title = '{:<10s}{:>10s}'.format(channel['name'], channel['Theme'])
            self.MainFrame.listWidget_2.addItem(title)

    def leaveRoom(self, text):
        name = text.split(' ')[0].strip()
        if self.udpSocket != None:
            reply = QMessageBox.question(self.MainWindow, 'Info', 'You are leaving Room {0}. Are you sure?'.format(self.current_channel_name),
                                         QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                print('Quit Room: ' + name)
                self.MainFrame.listWidget.clear()
                message = 'QUIT {name} {ip} {port}'.format(name=self.current_channel_name, ip=self.localIP, port=self.udpPort)
                self.tcpSocket.sendall(message.encode('utf-8'))
                self.socket_list.remove(self.udpSocket)
                self.udpSocket = None
                self.room = None
                time.sleep(1)
            else:
                return self.room
        else:
            QMessageBox.question(self.MainWindow, 'Info',
                                             'You have to enter a Room first.')
        self.MainFrame.groupBox_2.setTitle('Room')

    def enterRoom(self, text):
        name = text.split(' ')[0].strip()
        if self.udpSocket != None:
            if name != self.current_channel_name:
                reply = QMessageBox.question(self.MainWindow, 'Info', 'You need to quit Room {0} first. Are you sure?'.format(self.current_channel_name),
                                             QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    print('Quit Room: ' + name)
                    self.MainFrame.listWidget.clear()
                    message = 'QUIT {name} {ip} {port}'.format(name= self.current_channel_name, ip=self.localIP, port=self.udpPort)
                    self.tcpSocket.sendall(message.encode('utf-8'))
                    self.socket_list.remove(self.udpSocket)
                    self.udpSocket = None
                    time.sleep(1)
                else:
                    return self.room
        self.MainFrame.groupBox_2.setTitle('Room:' + name)
        if name != self.current_channel_name:
            print('Enter Room: ' + name)
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
                    self.room = Room(name, self.udpSocket, self.serverUdpAddr)
                    return self.room
        else:
            return self.room
        return self.room

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
        self.room = None  #

    def closeEvent(self, *args, **kwargs):
        self.client.exitAPP()

    def MessageBox(self):
        reply = QMessageBox.information(self, 'Info',
                                     'Disconnected from chat server!', QMessageBox.Yes)

    def sendMessage(self):
        if self.client.room != None:
            text = self.ui_Window.plainTextEdit.toPlainText()
            marchtObj = re.match(r'@(.*?):(.*?):(.*?)', text, re.S | re.M)
            if marchtObj:
                str_message = '[Private] {}:{}：   {}'.format(marchtObj.group(1), int(marchtObj.group(2)), text[len(marchtObj.group(0)):])
                self.client.MainFrame.listWidget.addItem(str_message)

            self.room.sendMessage(self.ui_Window.plainTextEdit.toPlainText())
            self.ui_Window.plainTextEdit.clear()
        else:
            reply = QMessageBox.information(self, 'Info', 'You need to enter a Room first.',
                                         QMessageBox.Yes)

    def leaveRoom(self):
        if self.client.room != None:
            # print(self.client.room.name)
            self.client.leaveRoom(self.client.room.name)
        else:
            reply = QMessageBox.information(self, 'Info', 'You need to enter a Room first.',
                                         QMessageBox.Yes)

    def clickUserList(self, item):
        user = item.text()
        self.ui_Window.plainTextEdit.setPlainText('@' + user + ": ")

    def enterRoom(self, item):
        channel = item.text()
        self.room = self.client.enterRoom(channel)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWindow = ClientWindowDlg()
    mainWindow.show()
    sys.exit(app.exec_())