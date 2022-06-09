##########################################################
#                                                        #
# example for a GUI build with tkinter                   #
#                                                        #
# this assumes, that a PTR instrument is connected to    #
# the local computer and is running a 'webAPI' server    #
#                                                        #
##########################################################
try:
    import pytrms
except ModuleNotFoundError:
    # find module if running from the example folder
    # in a cloned repository from GitHub:
    sys.path.insert(0, join(dirname(__file__), '..'))
    import pytrms

import tkinter as tk
from tkinter import (
        Button,
        END,
        Entry,
        Frame,
        Label,
        Menu,
        messagebox,
        StringVar,
        Text,
        Tk
)

import matplotlib
matplotlib.use('TKAgg')

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (
        FigureCanvasTkAgg,
        NavigationToolbar2Tk
        )


class MainFrame(Frame):

    def __init__(self, master=None):
        Frame.__init__(self, master)   
        self.master = master
        self.ptr = None

        self.host_var = StringVar()
        self.port_var = StringVar()
        self.info_string = StringVar()

        self.init_window()

    def init_window(self):

        self.master.title("Ionicon webAPI Example")

        # allow the widget to take the full space of the root window:
        self.pack()

        self.master.config(menu=self.make_menu())

        label1 = Label(self.master, text="IP Address:")
        label1.pack()
        self.host_var.set('localhost')
        txt = Entry(self.master, textvariable=self.host_var)
        txt.pack()

        label2 = Label(self.master, text='Port:')
        label2.pack()
        self.port_var.set('8002')
        txt = Entry(self.master, textvariable=self.port_var)
        txt.pack()

        buttonConnect = Button(self.master, text="Connect",command=self.connect)
        buttonConnect.pack()

        buttonDisconnect = Button(self.master, text="Disconnect",command=self.disconnect)
        buttonDisconnect.pack()

        self.info_string.set("")
        info_label = Label(self.master, textvariable=self.info_string)
        info_label.pack()
    
    def make_menu(self):
        menu = Menu(self.master)

        file_menu = Menu(menu)
        file_menu.add_command(label="Exit", command=self.client_exit)

        menu.add_cascade(label="File", menu=file_menu)

        mb_menu = Menu(menu)
        mb_menu.add_command(label="Connect", command=self.connect)
        mb_menu.add_command(label="Disconnect", command=self.disconnect)

        menu.add_cascade(label="Modbus", menu=mb_menu)

        return menu

    def client_exit(self):
        exit()

    def connect(self):
        try:
            host, port = self.host_var.get(), int(self.port_var.get())
        except ValueError as exc:
            print(exc)
            return

        self.ptr = pytrms.connect(host, port)
        if self.ptr is None:
            self.disconnect()
            return 

        self.info_string.set(str(self.ptr))

    def disconnect(self):
        self.plot_smth()
        return 

        self.ptr = None
        self.info_string.set('disconnected')

    def plot_smth(self):
        figure = Figure(figsize=(3,2), dpi=100)

        figure_canvas = FigureCanvasTkAgg(figure, self)

        NavigationToolbar2Tk(figure_canvas, self)

        axes = figure.add_subplot()

        
        axes.plot([3,4,7,1,2,5])
        axes.set_title('my title')

        figure_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

if __name__ == '__main__':

    root = Tk()
    root.geometry("640x480")
    
    app = MainFrame(root)
    
    app.mainloop() 

