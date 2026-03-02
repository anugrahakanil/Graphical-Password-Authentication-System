import os
import datetime
from tkinter import *
from tkinter.ttk import *
from PIL import ImageTk, Image


def getCredentialImages():
    imagePaths = os.listdir("credentialImages")
    return imagePaths[:-1] # last file is txt file, don't need thats