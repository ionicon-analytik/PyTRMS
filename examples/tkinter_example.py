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

import matplotlib
matplotlib.use('TKAgg')

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (
        FigureCanvasTkAgg,
        NavigationToolbar2Tk
)

from numpy.random import random


class MainFrame(tk.Frame):

    def __init__(self, master=None):
        tk.Frame.__init__(self, master)   
        self.master = master
        self.ptr = None

        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar()
        self.info_string = tk.StringVar()

        self.init_window()

    def init_window(self):

        self.master.title("Ionicon webAPI Example")

        # allow the widget to take the full space of the root window:
        self.pack()

        self.master.config(menu=self.make_menu())

        label1 = tk.Label(self.master, text="IP Address:")
        label1.pack()
        self.host_var.set('localhost')
        txt = tk.Entry(self.master, textvariable=self.host_var)
        txt.pack()

        label2 = tk.Label(self.master, text='Port:')
        label2.pack()
        self.port_var.set('8002')
        txt = tk.Entry(self.master, textvariable=self.port_var)
        txt.pack()

        buttonConnect = tk.Button(self.master, text="Connect",command=self.connect)
        buttonConnect.pack()

        buttonDisconnect = tk.Button(self.master, text="Disconnect",command=self.disconnect)
        buttonDisconnect.pack()

        buttonPlot = tk.Button(self.master, text="Plot",command=self.plot_smth)
        buttonPlot.pack()

        self.info_string.set("")
        info_label = tk.Label(self.master, textvariable=self.info_string)
        info_label.pack()

        self.figure = Figure(figsize=(3,2), dpi=100)
        figure_canvas = FigureCanvasTkAgg(self.figure, self)
        #NavigationToolbar2Tk(figure_canvas, self)
        self.axes = self.figure.add_subplot()
        self.axes.set_title('my title')
        self.axes.set_ylim([0,1])
        self.line, = self.axes.plot(random(5))
        figure_canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=1)
    
    def make_menu(self):
        menu = tk.Menu(self.master)

        file_menu = tk.Menu(menu)
        file_menu.add_command(label="Exit", command=self.client_exit)

        menu.add_cascade(label="File", menu=file_menu)

        webAPI_menu = tk.Menu(menu)
        webAPI_menu.add_command(label="Connect", command=self.connect)
        webAPI_menu.add_command(label="Disconnect", command=self.disconnect)

        menu.add_cascade(label="webAPI", menu=webAPI_menu)

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

        self.info_string.set(str(self.ptr.get('TPS_Push_H')))

    def disconnect(self):
        self.ptr = None
        self.info_string.set('disconnected')

    def plot_smth(self):

        self.line.set_ydata(random(5))
        # The data limits are not updated automatically when artist data are changed after
        # the artist has been added to an Axes instance. In that case, use
        # matplotlib.axes.Axes.relim() prior to calling autoscale_view.
        self.axes.relim()
        # Autoscale the view limits using the data limits (if `tight=True`, only expand
        # the axis limits using the margins):
        #self.axes.axes.autoscale_view(tight=True, scalex=True, scaley=True)
        # If the views of the Axes are fixed, e.g. via set_xlim, they will not be changed
        # by autoscale_view(). See matplotlib.axes.Axes.autoscale() for an alternative.

        # Update the figure and react to events:
        self.figure.canvas.draw()
        self.figure.canvas.flush_events()


if __name__ == '__main__':

    root = tk.Tk()
    root.geometry("640x480")
    
    app = MainFrame(root)
    
    app.mainloop() 

